---
title: calico getting start
date: 2017-03-16 20:02:16
tags: [network, calico]
---

# 简介

[Calico](https://www.projectcalico.org/)是一个纯3层虚拟网络，可以为夸主机的容器/虚拟机等提供网络访问，同时支持IPv4和IPv6。并且可以根据策略提供访问控制能力。

Calico的工作原理主要依靠linux本身提供的ip转发机制，不需要虚拟交换设备或者overlay支持。每一个主机都会将自己的路由信息告知数据中心网络中的其他主机：在小型网络中，直接通过BGP协议交换信息；在大型网络中，通过BGP route reflectors完整路由信息的交换。

Calico为各个不同的云环境提供了不同的插件来使用calico网络，kubernetes和mesos通过CNI插件形式使用calico，docker使用libnetwork插件使用calico网络进行跨主机容器间通信。OpenStack使用Neutron插件使用calico。

# 入门实践

## 环境搭建

这里根据[官网教程](http://docs.projectcalico.org/v2.0/getting-started/docker/installation/vagrant-ubuntu/)使用vagrant进行docker+calico初始环境搭建。官方文档还提供了手动环境搭建的流程，但是由于一些坑（跨主机容器不能相互访问）放弃了，后来在vagrant上解决了也懒得重新解决一遍了。

搭建命令如下

```shell
# 需要在主机上有git/vagrant/virtualbox
git clone https://github.com/projectcalico/calico.git
cd calico/v2.0/getting-started/docker/installation/vagrant-ubuntu
# 初始化虚拟机环境，此命令会创建两个主机calico-01/calico-02，且在01上运行了etcd
vagrant up
# 验证环境
vagrant ssh calico-01 # ssh into calico-01 host
ping 172.17.8.102 # ping calico-02 in calico-01
# run calico/node
sudo calico node run
# 查看运行
docker ps
exit # exit from calico-01
vagrant ssh calico-02 # ssh into calico-02 host
sudo calico node run
# 查看BGP信息
sudo calico node status
exit
```

上诉能ping通且`sudo calico node status`能显示对端的信息说明环境搭建成功。

## 测试工作

安装[官方文档](http://docs.projectcalico.org/v2.0/getting-started/docker/tutorials/simple-policy)的说明，跨主机的容器通信很简单。只要给docker创建calico的network，然后创建container时设置这个network就可以。具体如下：

```shell
# 进入calico-01，创建docker网络
docker network create --driver calico --ipam-driver calico-ipam net1
# 创建容器并设置网络为net1
docker run -d --net net1 --name workload-A busybox tail -f /etc/hosts
# 查看容器ip地址
docker exec -it workload-A ip a # 查看到calixxx网络的地址为IP1
# 进入calico-02，查看docker网络
docker network ls # 运行这条命令可以看到net1的网络
# 创建容器
docker run -d --net net1 --name workload-B busybox tail -f /etc/hosts
# 在calico-02的容器中ping calico-01的容器地址
docker exec -it workload-B ping workload-A
docker exec -it workload-B ping $IP1
# 也可以直接在calico-02上ping calico-01的容器地址
ping $IP1
```

按照官方文档的说明，这里应该是能直接ping通的，但是这里就出现了上面一开始就说到的坑，并不能ping通，只有通一个主机的两个container直接可以ping。这个坑我首先在自己的azure上手动安装环境时就遇到了，同事帮忙查看了好久，看了iproute, iptables的各种信息，并用tcpdump进行抓包，但是都无法解决，认为可能是azure的问题。于是我又在自己的机器上安装使用virtualbox安装了两个虚拟机，结果还是一样。最后在Mac上直接使用vagrant也无效。这个问题直接浪费了我至少两天时间。最近同事终于发现原来是iptables会把这些包给drop掉。。。而解决这个问题的方法是需要设置calico的profile和policy对象，使得出入流量可以在两个主机之间互通。

```shell
# 配置net1网络。在docker创建net1时就创建了这个profile，这里我们更改一些属性！
cat << EOF | calicoctl apply -f -
- apiVersion: v1
  kind: profile
  metadata:
    name: net1
    labels:
      role: net1
EOF

# 为net1创建policy，运行所有出入流量！
cat << EOF | calicoctl create -f -
- apiVersion: v1
  kind: policy
  metadata:
    name: net1
  spec:
    order: 0
    selector: role == 'net1'
    ingress:
    - action: allow
    egress:
    - action: allow
EOF

```

通过上面的设置，终于可以愉快的跨主机通信了^_^。
查看`ip route`可以发现，本地的ip直接走本地的calico创建的veth设备，其他主机的ip通过网卡直接路由到目标主机ip，然后交给目标主机的路由表处理。

```
default via 10.0.2.2 dev enp0s3
10.0.2.0/24 dev enp0s3  proto kernel  scope link  src 10.0.2.15
172.17.8.0/24 dev enp0s8  proto kernel  scope link  src 172.17.8.101
172.18.0.0/16 dev docker0  proto kernel  scope link  src 172.18.0.1 linkdown
# 目的地址为192.168.50.64/26的请求通过主机上的enp0s8网卡发到172.17.8.102
192.168.50.64/26 via 172.17.8.102 dev enp0s8  proto bird
blackhole 192.168.84.192/26  proto bird
# 本机container直接打到对应设备上
192.168.84.209 dev calic18c1dc57ca  scope link
```

## ipip 隧道通信

calico支持两个container之间通过ipip隧道通信。在这种模式下，calico会为我们在主机上创建tunl0设备。使用这个设备进行ip封装和拆解。

在打开ipip选项之前，可以先试用`ip link`看一下机器上的设备被没有tunl0设备。通过下面步骤打开

1. 执行`calicoctl config set ipip on`, 打开设置
2. 按照[这里](http://docs.projectcalico.org/v2.0/usage/troubleshooting/faq#how-do-i-enable-ipip-and-nat-outgoing-on-an-ip-pool)的教程打开ipPool的ipip

```shell
calicoctl get ipPool -o yaml > pool.yaml
# 修改spec内容，设置ipip和nat-outgoing

- apiVersion: v1
  kind: ipPool
  metadata:
    cidr: 192.168.0.0/16
  spec:
    ipip:
      enabled: true
    nat-outgoing: true

calicoctl replace -f pool.yaml
```

通过上诉设置，就打开了calico的ipip支持。查看`ip route`可以看到和原来的不同:

```
default via 10.0.2.2 dev enp0s3
10.0.2.0/24 dev enp0s3  proto kernel  scope link  src 10.0.2.15
172.17.8.0/24 dev enp0s8  proto kernel  scope link  src 172.17.8.101
172.18.0.0/16 dev docker0  proto kernel  scope link  src 172.18.0.1 linkdown
# 注意这里使用到tunl0设备，与前面不同
192.168.50.64/26 via 172.17.8.102 dev tunl0  proto bird onlink
blackhole 192.168.84.192/26  proto bird
# 本机container直接打到对应设备上
192.168.84.208 dev cali445d36d1804  scope link
```

现在跨主机的通信通过tunl0设备而不是原来的enp0s8设备了。

这样ping容器时进行`tcpdump -i tunl0 icmp`可以看到有icmp包。`tcpdump -i cali445d36d1804 icmp`可以看到流量。

`tcpdump -i enp0s8 | grep ipip`同样可以看到ipip报文，内容如图所示：

```
06:35:48.321025 IP 172.17.8.102 > 172.17.8.101: IP 192.168.50.97 > 192.168.84.208: ICMP echo request, id 2304, seq 0, length 64 (ipip-proto-4)
06:35:48.321149 IP 172.17.8.101 > 172.17.8.102: IP 192.168.84.208 > 192.168.50.97: ICMP echo reply, id 2304, seq 0, length 64 (ipip-proto-4)
06:35:49.322821 IP 172.17.8.102 > 172.17.8.101: IP 192.168.50.97 > 192.168.84.208: ICMP echo request, id 2304, seq 1, length 64 (ipip-proto-4)
06:35:49.322900 IP 172.17.8.101 > 172.17.8.102: IP 192.168.84.208 > 192.168.50.97: ICMP echo reply, id 2304, seq 1, length 64 (ipip-proto-4)
```

## 性能测试

这里简单的测试了calico网络的性能。测试环境是MacBook上创建的两个虚拟机。calico网络使用networkstatic/iperf3进行性能测试，host之间也适用iperf3测试。测试结果如下：

测试项 | 命令 | Bandwidth | Retr
---- | --- | --- | ---
主机网络 | `iperf3 -c 172.17.8.101 -n 10000M -O 3` | 2.25 Gbits/sec | 55672
docker host | `docker run --rm -it --net host networkstatic/iperf3 -c 172.17.8.101 -n 10000M -O 3` | 2.22 Gbits/sec | 55285
calico | `docker run --rm -it --net net1 networkstatic/iperf3 -c 192.168.84.209 -n 10000M -O 3` | 2.09 Gbits/sec | 36470
calico-ipip | `docker run --rm -it --net net1 networkstatic/iperf3 -c 192.168.84.208 -n 10000M -O 3` | 2.15 Gbits/sec | 4516

可以看到ipip的性能还要稍微好于非ipip模式，且在ipip模式下TCP的重传较少。总体来看，对比host模式，calico的性能损失不大。

对于上面的测试结果（ipip模式比非ipip模式要好）存在疑惑，因为实际上相比于非ipip模式，ipip模式下需要多经历一次ip包的封装。针对这个疑惑我在社区提了个[issue](https://github.com/projectcalico/calico/issues/621)。根据回复中的建议在iperf命令中加入了`-M 1440`设置mtu参数，结果显示非ipip模式实际是要比较好的，这比较符合常理。（注：1440是calico的tunl0的mtu值）

# 自己动手
calico实际上就是对本机容器ip在主机上建立路由，并将这些路由通过bgp协议告知其他主机。通过路由表的信息，达到主机垮主机的容器通信。
下面使用同事给的demo使用linux的ip命令工具来模拟calico的非ipip网络和ipip网络。

1. 首先创建两个虚拟机host1(dev enp0s8:172.17.8.101)和host2(dev enp0s8:172.17.8.102)，检查是否可以相互ping通
2. 在host1上执行以下命令创建容器网络

  ```shell
  # netns内部ip, 假设本机上所有container的网段在192.168.41.0/24
  ip=192.168.41.2
  ctn=ctn1
  ip netns add $ctn
  ip li add dev veth_host type veth peer name veth_sbx
  ip link set dev veth_sbx netns $ctn
  ip netns exec $ctn ip ad add $ip dev veth_sbx
  ip netns exec $ctn ip link set dev veth_sbx up
  ip netns exec $ctn ip route add 169.254.1.1 dev veth_sbx
  ip netns exec $ctn ip route add default via 169.254.1.1 dev veth_sbx
  ip netns exec $ctn ip ad
  ip netns exec $ctn ip link set dev veth_sbx up
  ip link set dev veth_host up
  ip ad show veth_host
  ip netns exec $ctn ip neigh add 169.254.1.1 dev veth_sbx lladdr `cat /sys/class/net/veth_host/address` 
  ip route add $ip dev veth_host
  # 打开ip_forward
  echo 1 > /proc/sys/net/ipv4/ip_forward
  ```

3. 将上诉脚本的ip地址改为192.168.42.2，在host2执行
4. 执行以下步骤添加路由表项以达到跨主机container访问

  ```
  # 在host2执行下面命令
  ip route add 192.168.41.0/24 via 172.17.8.101 dev enp0s8
  # 在host1执行下面命令
  ip route add 192.168.42.0/24 via 172.17.8.102 dev enp0s8
  ```

5. 这样就可以在主机或者容器网络空间内ping跨主机的container ip了

  ```
  # 在host1 ping host2的container
  ip netns exec ctn1 ping 192.168.42.2
  ```

通过上诉步骤，就模拟了calico的默认网络。

通过之前的描述，calico实际还支持ipip模式的跨主机通信，原理就是通过tunnel设备对原始ip报文进行封装。只需要对上述脚本做一些修改就可以：

1. 在两台主机上将上诉过程中的第4步添加的路由规则去掉
2. 在host1上执行以下脚本

  ```shell
  ipip=192.168.41.3
  # 这个命令会生成一个tunl0设备
  modprobe ipip
  ip link set tunl0 up
  ip a add $ipip brd + dev tunl0
  # 注意这里的路由规则，前面已经提到过，使用tunl0设备！最后一个参数onlink是必须的，具体作用参考[这里](http://lartc.vger.kernel.narkive.com/XgcjFTGM/aw-onlink-option-for-ip-route)
  ip r add 192.168.42.0/24 via 172.17.8.102 dev tunl0 proto bird onlink
  ```

3. 在host2上执行类似上诉步骤
4. 重新进入网络空间ping跨主机container ip
5. 可以在对端的enp0s8网卡上使用tcpdump进行截包

  ```
  tcpdump -vvnneSs 0 -i enp0s8

  07:41:03.985150 08:00:27:d5:4b:b1 > 08:00:27:29:bc:de, ethertype IPv4 (0x0800), length 118: (tos 0x0, ttl 63, id 55151, offset 0, flags [DF], proto IPIP (4), length 104)
      172.17.8.101 > 172.17.8.103: (tos 0x0, ttl 63, id 16085, offset 0, flags [DF], proto ICMP (1), length 84)
      192.168.41.2 > 192.168.43.2: ICMP echo request, id 15973, seq 30, length 64
  07:41:03.985243 08:00:27:29:bc:de > 08:00:27:d5:4b:b1, ethertype IPv4 (0x0800), length 118: (tos 0x0, ttl 63, id 32595, offset 0, flags [none], proto IPIP (4), length 104)
      172.17.8.103 > 172.17.8.101: (tos 0x0, ttl 63, id 42711, offset 0, flags [none], proto ICMP (1), length 84)
      192.168.43.2 > 192.168.41.2: ICMP echo reply, id 15973, seq 30, length 64
  ```

ipip相对于非ipip模式会有一些性能的损失，但是好处在于ipip模式下可以进行跨网段的主机间容器通信！将上诉的脚本的两个不同网段的主机上测试可以验证这个结果。