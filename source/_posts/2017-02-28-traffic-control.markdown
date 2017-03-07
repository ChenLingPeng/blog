---
layout: post
title: Traffic control
tag: tc
---

# 简介

在linux环境下，可以利用tc命令工具对本地流量进行控制，主要通过限速（shaping），调度（scheduling）和策略（policing）进行流量的控制。
本文主要简略介绍tc中所使用到的几个概念，并结合命令示例对流量控制进行解释。由于tc主要用于出带宽的控制，所以下文主要描述的都是对出带宽的控制，文末附加一个利用tc进行入带宽控制的示例。

tc主要利用3种对象来达成对流量的控制，分别是qdisc（排队规则）, class（类别）, filter（分类器）。

## qdisc

qdisc可以看做是一个有规则的队列，内核如果需要网卡向外发送数据，首先需要放入队列中，然后内核从队列中取出。例如最简单的fifo队列，数据包通过这个队列会按照先进先出的顺序从队列中流出发送到网卡上。

qdisc按照类别划分可以分为有类别队列和无类别队列，其中有类别队列本身附着有类属性，并会根据分类器划分到类中，类可以继续划分为新的子类，如果不在继续分类，则需要为类指定一个队列。按照层次关系形成一棵类似于树状的结构，且树的叶子类节点需要附着一个无类型的队列。

常见的无类别队列有sfq(随机公平队列)，pfifo_fast，tbf（令牌桶）。

* sfq

sfq实现了高度的公平性，会为每个会话使用一个散列算法散列到有限的几个队列中，系统每次从每个队列中拿出流量进行发送。多个会话可能共享一个队列，sfq算法会定期更新散列算法，重新将会话放到新的队列中来达到随机的效果。

```shell
# 增加一个qdisc，父类为1:10，其自身ID为10:0，使用sfq，每10秒更换一次hash算法
tc qdisc add dev eth0 parent 1:10 handle 10: sfq perturb 10
```

* pfifo_fast

pfifo_fast队列可以看作是有类别队列prio的无类别（固定类别）版本，该队列规则内部已经定义了优先级且无法使用tc进行修改。
pfifo_fast内部有3个band，分别记为0，1，2。如果band0上还有数据包，则一直从这个band上取出直到没有后再去band1，以此类推。数据包是按照header中的服务类型TOS进行分配的。TOS是数据包上的一个4bit字段，具体规则如下（规则源自[lartc](http://www.lartc.org/lartc.html)）：

```
Binary Decimcal  Meaning
-----------------------------------------
1000   8         Minimize delay (md)
0100   4         Maximize throughput (mt)
0010   2         Maximize reliability (mr)
0001   1         Minimize monetary cost (mmc)
0000   0         Normal Service

由于其实TOS的这4bit是8(0-7)位中的1-4位，所以实际值是其2倍。

TOS     Bits  Means                    Linux Priority    Band
------------------------------------------------------------
0x0     0     Normal Service           0 Best Effort     1
0x2     1     Minimize Monetary Cost   1 Filler          2
0x4     2     Maximize Reliability     0 Best Effort     1
0x6     3     mmc+mr                   0 Best Effort     1
0x8     4     Maximize Throughput      2 Bulk            2
0xa     5     mmc+mt                   2 Bulk            2
0xc     6     mr+mt                    2 Bulk            2
0xe     7     mmc+mr+mt                2 Bulk            2
0x10    8     Minimize Delay           6 Interactive     0
0x12    9     mmc+md                   6 Interactive     0
0x14    10    mr+md                    6 Interactive     0
0x16    11    mmc+mr+md                6 Interactive     0
0x18    12    mt+md                    4 Int. Bulk       1
0x1a    13    mmc+mt+md                4 Int. Bulk       1
0x1c    14    mr+mt+md                 4 Int. Bulk       1
0x1e    15    mmc+mr+mt+md             4 Int. Bulk       1
```

* tbf

tbf队列利用令牌桶原理来控制出带宽，每流出一定的数据量，就需要消耗桶中的令牌，一旦令牌消耗完毕，则不会再继续发送数据。每个一段时间，会重新往桶里面添加令牌直到桶满为止。

```shell
tc qdisc add dev eth0 root tbf rate 0.5mbit \
burst 5kb latency 70ms peakrate 1mbit \
minburst 1540
```

常见的分类队列有prio和htb

* prio

prio队列与前面的pfifo_fast类似，高优先级的数据先发送。在创建prio时，系统默认就会创建3个类，这些类仅包含单纯的fifo队列，用户可以利用tc进行替换。

* htb

htb（Hierarchical Token Bucket）分层桶令牌与无类队列tbf类似，用于流量整形。

```shell
# 速率为30kbps，且上限（ceil）为100kps，说明如果网络空闲，这个class可以向外界借用宽带，默认ceil为rate一致
tc class add dev eth0 parent 1:2 classid 1:10 htb rate 30kbps ceil 100kbps
```

htb可以进行优先级划分，高优先级的队列优先得到剩余宽带，同优先级之间按照rate进行按比例划分。

## class

class存在于有类别队列中，class是可以包含多个子类或者一个子队列。叶子类在队列中属于最终类别，会默认包含一个fifo的qdisc。

## filter

filter的作用主要是定义如何将一个qdisc(class)划分到子class中。常见的分类器有u32。可以根据ip, 端口，协议类型，mac地址等进行过滤。

# 样例说明

在实际使用tc命令进行流量控制时，会为每个qdisc／class分配一个id，id由 主ID:从ID 两部分组成，其中qdisc的命名以主ID进行区分，例如 10: ,别是其ID为10:0，qdisc的从ID都是0。class的ID为10:1，其中主ID需要于其父节点ID一致。

## 出带宽控制

下面的例子来自[Linux高级流控](http://www.ibm.com/developerworks/cn/linux/1412_xiehy_tc/)

```shell
# 创建htb，默认走1:30的类别
tc qdisc add dev eth0 root handle 1: htb default 30
# 为root qdisc创建1:1的类别，注意主ID为1，与parent一致
tc class add dev eth0 parent 1: classid 1:1 htb rate 6mbit burst 15k
# 在class 1:1下定义3个子class，注意子class的主ID与parent一致
tc class add dev eth0 parent 1:1 classid 1:10 htb rate 5mbit burst 15k
tc class add dev eth0 parent 1:1 classid 1:20 htb rate 3mbit ceil 6mbit burst 15k
tc class add dev eth0 parent 1:1 classid 1:30 htb rate 1kbit ceil 6mbit burst 15k
# 为每个叶子class定义sfq的qdisc，防止流量被某个连接占用。perturb表示几秒更换一次hash算法。
tc qdisc add dev eth0 parent 1:10 handle 10: sfq perturb 10
tc qdisc add dev eth0 parent 1:20 handle 20: sfq perturb 10
tc qdisc add dev eth0 parent 1:30 handle 30: sfq perturb 10
# 添加u32过滤器, 直接把流量导向相应的类 :
U32="tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32"
$U32 match ip dport 80 0xffff flowid 1:10
$U32 match ip sport 25 0xffff flowid 1:20
```

另外，使用以下命令可以查看各个qdisc/class的流量情况：

```shell
tc -s -d qdisc show dev eth0
tc -s -d class show dev eth0
```

## tc + cgroup

可以利用cgroup来进行进程的流量控制。使用cgroup进行流量控制时，需要引入net_cls cgroup子模块，在net_cls.classid文件中定义好该group下进程的分类class id。并在定义filter时使用cgroup filter

```shell
tc filter add dev eth2 parent 10: protocol ip prio 10 handle 1: cgroup
```

## 入带宽控制

一般使用tc进行出带宽控制，因为tc的入带宽控制从网卡拿数据时数据已经发送到本机，再进行控制显得没有太多意义。下面仅演示利用tc ingress进入入带宽控制

```shell
tc qdisc add dev eth0 handle ffff: ingress
# 限制来子10.0.0.*来的流量
tc filter add dev eth0 parent ffff: protocol ip prio 50 u32 match ip src 10.0.0.1/24 police rate 100kbit burst 10k drop flowid :1
```

# 其他

流量测试数据可以使用 http://cachefly.cachefly.net/100mb.test 进行测试

# 参考资料

1. [Linux Advanced Routing & Traffic Control HOWTO](http://www.lartc.org/lartc.html)
2. [Traffic Control HOWTO](http://www.tldp.org/HOWTO/html_single/Traffic-Control-HOWTO/)
3. [Linux 高级流控](http://www.ibm.com/developerworks/cn/linux/1412_xiehy_tc/)
4. [htb user guide](http://luxik.cdi.cz/~devik/qos/htb/manual/userg.htm)
5. [tc-tbf](https://linux.die.net/man/8/tc-tbf)
