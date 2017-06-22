---
title: sriov getting start
date: 2017-06-22 11:28:56
tags: [network]
---

# 前言

最近在调研SR-IOV的使用，准备作为CNI插件用在kubernetes的Pod网络上。这篇文章是对SRIOV基础操作的介绍，通过介绍可以了解SRIOV的使用。

# 简介

SR-IOV是网卡支持的一种硬件IO虚拟化方案，简单的说就是可以将一个物理网卡虚拟成多个物理网卡设备。
SR-IOV引入了PFs(physical functions)和VFs(virtual functions)的概念，每个VF都可以看做是一个独立的物理网卡(PCIe设备)可以被容器或虚拟机直接访问，从而提升性能。相比于传统的veth+bridge实现容器网络，除了性能上的优势之外，SR-IOV的另一个优点就是隔离性好，各个VF是独立的，发往VF的请求不会经过PF，所以不会被主机上的PF网卡嗅探到。

# 使用

当前公司的物理机一般都支持SR-IOV，但是并未开启。各个网卡类型支持的VF数量不同，在使用之前通过以下命令先查看物理网卡eth1最多支持几个VF
`cat /sys/class/net/eth1/device/sriov_totalvfs`

根据需要开启vf设备如开启7个vf设备
`echo 7 > /sys/class/net/eth1/device/sriov_numvfs`

开启之后，在机器上`ip link`就可以看到新增了7个设备ethX。

这里需要注意VF设备是不能增量添加的，如果需要修改启动的VF数量，需要先将sriov_numvfs值重置为0后再重新设置为目标值，所以在使用SR-IOV功能最好能确定最多会使用到几个VF，以防在业务运行过程中需要扩展VF数影响正在使用VF的业务。

开启SR-IOV功能后，在/sys/class/net/eth1/device目录下会多出多个virtfnX的目录，这些目录下分别记录了对应VF的信息，例如可以通过`ls /sys/class/net/eth1/device/virtfn*/net`显示对应vf设备名称,如下图所示：

![sriov](/images/sriov01.png)

如果VF已经被放入了其他网络名字空间，那么net目录下会显示为空，例如上图中的virtfn0。

容器使用vf设备，只需要使用`ip link set dev $VF netns $NET_NS`将vf设备放入容器所在网络名字空间，配置浮动IP和对应路由规则并将设备UP即可。

通过上诉的说明，已经可以使用VF为容器提供网络功能了。

# 优化

实验过程中发现开启SR-IOV后会对原先的多队列网卡有影响（关于多队列网卡这里不做介绍）。在开启之前，eth1根据不同网卡型号可能有8-24个队列，开启之后接收队列会可能会减少到两个，且此时默认情况下所有vf的硬中断都会集中在同一个CPU上，导致在请求较多的情况下使得CPU成为可能存在的瓶颈。为了缓解这个问题，可以将各个vf的队列分布到不同的CPU上处理。首先通过以下命令得到各个vf的中断号
`ls /sys/class/net/eth1/device/virtfn0/msi_irqs/`
如果知道vf设备名称，也可以直接`ls /sys/class/net/eth4/device/msi_irqs/`获取中断号，不过这种方式需要设备在当前网络空间，如果设备在容器里，主机上是没有eth4这个目录的。
得知中断号后可以给中断号绑定不同的CPU，以下命令将将中断号为77的硬中断交给CPU1处理
`echo 1 > /proc/irq/77/smp_affinity_list`

除了设置硬中断CPU，根据业务场景需要，还可以使用CPU位掩码将网卡队列的软中断处理均衡到不同的CPU上，例如`echo f > /sys/class/net/$dev/queues/rx-0/rps_cpus`将$dev的接收队列rx-0发生的软中断绑定到0-3号CPU上

# 性能测试

使用SR-IOV的一个主要原因就是因为它通过硬件虚拟化来加速容器收包的速度，所以需要对性能进行验证。

由于资源条件限制，我们只拿到了一台支持sriov的万兆网卡机器，为了测试其性能，我们同时用6个千兆网卡机器使用netperf进行性能对比测试。
在万兆网卡上，根据虚拟比1:6启动了6个网络名字空间，每个名字空间内启动一个netserver。
在6个客户端上，分别为每个容器启动200个netperf进程，分别测试TCP_RR(64,64)和TCP_CRR(64,64)在使用SR-IOV和veth+bridge模式下的性能。
测试结果：
在开启sriov后，TCP_RR包量达到108万，相对于veth+bridge方式提升约15%. TCP_CRR包量达到8.1万，相对于veth+bridge方法提升约10%

# CNI插件

这部分工作其实[社区](https://github.com/Intel-Corp/sriov-cni)已经有了，我们在做的时候也参考了它的代码实现。思路很简单，在初次使用时将SR-IOV功能开启，为容器分配网络时从主机上挑选一个未使用的VF给容器使用，设置floatingip和相关路由，最后UP。当删除容器网络时，将设备重命名并归还到主机上即可。