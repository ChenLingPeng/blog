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
主机网络 | iperf3 -c 172.17.8.101 -n 10000M -O 3 | 2.25 Gbits/sec | 55672
docker host | docker run --rm -it --net host networkstatic/iperf3 -c 172.17.8.101 -n 10000M -O 3 | 2.22 Gbits/sec | 55285
calico | docker run --rm -it --net net1 networkstatic/iperf3 -c 192.168.84.209 -n 10000M -O 3 | 2.09 Gbits/sec | 36470
calico-ipip | docker run --rm -it --net net1 networkstatic/iperf3 -c 192.168.84.208 -n 10000M -O 3 | 2.15 Gbits/sec | 4516

可以看到ipip的性能还要稍微好于非ipip模式，且在ipip模式下TCP的重传较少。总体来看，对比host模式，calico的性能损失不大。
