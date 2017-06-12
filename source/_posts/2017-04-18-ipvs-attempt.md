---
title: ipvs attempt
date: 2017-04-18 16:45:48
tags: [network, kubernetes]
---

# 前序

k8s社区最近提了一个[issue](https://github.com/kubernetes/kubernetes/issues/44063), 说的是huawei使用ipvs代替kube-proxy中的iptables模式作为service的负载均衡。根据我们组实际的情况，对ipvs整合k8s方案进行了一些尝试。

为什么希望使用ipvs来替换iptables？
1. ipvs的目标就是lb，有更多的lb算法支持；而iptables主要作为防火墙软件。
2. 效率问题：在service较多的情况下，ipvs的效率比iptables要高。原因是在iptables中规则是顺序遍历的，而ipvs使用hash查找对应的规则进行lb。

ipvs相关的知识不在这里进行介绍，简单说明一下：
ipvs是L4负载均衡，主要有3种模式：NAT, TUN, DR. 每种都有其优缺点：

1. NAT 模式下会对请求包在LB上进行DNAT，对RS上的回包进行SNAT，NAT本身就消耗资源，另外请求和回复都经过LB，使得请求多的情况下LB会成为瓶颈；另外在架构上，NAT模式要求设置RS的默认路由指向RS，不是很友好。但是能进行端口转化，在k8s里面这是必须的（service-port和pod-port可以不一样）。
2. TUN 模式使用ip tunnel技术，对到达LB上的请求进行IP封包，再交给RS，RS处理后直接回包到client。这种方式的优势是只要两个节点本身是通的就可以使用这种模式。缺点是增加了tunnel的开销，并且无法做到端口转化。还有就是使用IPIP协议后，无法很好的使用多队列网卡特性来支持多CPU接收数据。
3. DR(direct-routing) 直接修改请求的目的MAC地址将包路由到RS上，相比于TUN模式减少了tunnel的开销。但是需要LB和RS在同一个子网下，而且也无法做到端口的转化

根据上诉的描述，只有NAT模式支持端口的转化，而在k8s中servicePort和podPort又可以是不同的，所以必然会用到端口转化，所以在这里只能选择NAT模式。下面对NAT进行尝试（探坑），看看是否能够替代iptables满足k8s的需求。

# 实践

现在lvs已经是内核的一部分了，所以一般我们不需要对内核重新编译加入lvs。
实验环境下我们需要安装ipvsadm命令工具来操作rule。

实验的环境基础采用之前博客里用脚本模拟的calico网络，使用ipip模式进行容器跨节点的通信。

首先确定一个vip模拟serviceIP，需要将这个vip加到本地的网卡上(ipvs需要规则中的地址为本地地址，可以随意选择网卡，如lo设备)
然后就可以使用ipvsadm在host1上建立NAT规则了。

```shell
ipvsadm -A -t $vip:80 -s rr
ipvsadm -a -t $vip:80 -r $remote_container_ip:8000 -m
```

非常简单，这样只会在本机的容器网络空间里面就可以通过这个vip访问另一主机上容器中的服务了。
例如本机ip为host1_ip容器的ip为container1_ip, 远端机器为host2_ip和container2_ip。在container2上启动一个webserver。
在container1内发起http请求，可以得到结果。
在host1上进行抓包，这里我们主要观察一下ipvs是如何起作用的，抓包命令为
`tcpdump -vvnneSs 0 -i any host container1_ip`
这里选择在host1上观察自己container请求流向，抓包情况如下

1. 首先看到`container1_ip:{随机端口}->vip的请求`
2. 然后经过ipvs模块的DNAT，请求变成了`container1_ip:{随机端口}->container2_ip`
3. 然后就是正常的container之间的通信了，即通过tunnel设备进行封装后发送到远程主机处理并返回
4. 接着看到`container2_ip->container1_ip:{随机端口}`的回来的请求，这里其实已经经过了本机的tunnel进行ipip包的解封了
5. 回来的包也会被ipvs模块的SNAT处理，将请求改写为`vip->container1_ip:{随机端口}`，最后发送到容器中

可以看出一个来回其实都会经过director-server进行DNAT和SNAT

上面的方法已经走通了container之间跨机service通信，但是有两个缺陷没法解决：

1. 需要往网卡上添加serviceIP，不确定地址太多会不会有额外的问题，暂时可以忽略（看到说可以使用local路由表来实现）
2. k8s要求可以在节点主机上通过serviceIP对容器进行访问，但是上诉的配置无法做到这一点

针对问题2在上诉的测试环境中进行抓包，发现问题主要出在在主机上发起请求的时候源IP地址也是vip，即如果发起请求`curl $vip`, 其初始的请求会是 `$vip->$vip`(这里涉及到了初始化请求时的地址选择)，然后经过ipvs模块后变成`$vip->container2_ip`并发送到远端，远端抓包可以发现这个请求，但是发现并没有交给用户空间进程进行处理（这里涉及到linux对请求的策略，linux会预判这个请求来回的路径是否一致，如果请求在设备1上接收，但是会在设备2上发出，就判定这个请求可能是不合法的，需要禁止`net.ipv4.rp_filter`），而且这里即使处理也是无法返回的，因为返回的请求是`container2_ip->$vip`,而不是发回给主机1.所以为了解决这个问题，主要需要将主机1请求的源地址进行改写，尝试使用iptables规则后失败了，网上查阅可能的原因是被ipvs处理的流量不会再进入iptables规则，详见[这里](http://zh.linuxvirtualserver.org/node/2245)！后来发现需要开启`net.ipv4.vs.conntrack`，并使用iptables的ipvs匹配模块对请求进行SNAT。

至此，ipvs就可以完成原来iptables对ClusterIP类型service的处理了，而对于NodePort来说更加简单，nodePort的地址已经存在于主机上，可以省略设置ip的步骤。

从上面的步骤来看ipvs可以完成原来iptables的负载均衡工作，目前huawei也已经提交了[PR](https://github.com/kubernetes/kubernetes/pull/46580)和[proposal](https://github.com/kubernetes/community/pull/692)





