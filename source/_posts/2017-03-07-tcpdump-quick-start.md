---
title: tcpdump quick start
date: 2017-03-07 19:41:31
tags:
---

tcpdump是linux上用于截获数据包的分析工具，提供了强大的包过滤和展示功能

tcpdump的用法主要是`tcpdump [option] [expression]`

## option

-A
以ASCII码方式展示数据包，不显示链路层header信息

-c count
指定tcpdump抓取count格数据包

-e
打印数据包的数据链路层header信息

-F file
以文件中的过滤表达式作为过滤条件

-i interface
监听网卡，使用any可以监听所有网卡。需要注意的是如果真实网络接口不能工作在'混杂'模式(promiscuous)下,则无法在'any'这个虚拟的网络接口上抓取其数据包？

-l
行缓冲输出，遇到换行符就输出

-q
简短的信息输出

-r file
从文件中读取包信息，如果file为-，则从标准输入中读取

-t
不打印时间戳

-tt
打印时间戳，秒数

-ttt
打印当前行和之前行的时间差

-tttt
打印时间戳，年月日形式

-ttttt
打印当前行和第一行的时间差

-v
当分析和打印的时候, 产生详细的输出. 比如, 包的生存时间, 标识, 总长度以及IP包的一些选项. 这也会打开一些附加的包完整性检测, 比如对IP或ICMP包头部的校验和.

-vv
产生比-v更详细的输出. 比如, NFS回应包中的附加域将会被打印, SMB数据包也会被完全解码.

-vvv
产生比-vv更详细的输出. 比如, telent 时所使用的SB, SE 选项将会被打印, 如果telnet同时使用的是图形界面,其相应的图形选项将会以16进制的方式打印出来(nt: telnet 的SB,SE选项含义未知, 另需补充).

-x
打印每个包的头部数据，不打印链路层头部信息

-xx
在-x的基础上还打印了链路层的头部信息


## expression

除了以上参数，tcpdump还可以在命令最后加上包过滤表达式，之后这个表达式为True的包才会被打印。这个表达式可以用于过滤协议，ip，端口等包数据
表达式是一个逻辑语句，可以用 and,or,not 连接。

`[ip|arp|rarp|ip6] [dst|src] host host1` 目的地址/源地址是host1，可以是名字或者ip地址。没有dst/src表示源或者目的地址

`ether [dst|src|host] ehost` 匹配以太网地址

`[src|dst] port port1` 端口过滤

`[tcp|udp] [src|dst] portrange port1-port2` 端口范围过滤

`[greater|less] length` 数据包长度小于大于length

`ip proto protocol` 协议过滤，如icmp6 igmp igrp udp tcp icmp等。由于udp tcp icmp在tcpdump中是关键字，需要用\tcp来转义.

`ip broadcast` 过滤广播数据

`ip multicast` 过滤多播数据


例子：
`dst host 10.100.10.1 and (ip proto \udp or src port 80)`




## 参考

1. http://www.tcpdump.org/tcpdump_man.html

2. http://www.tcpdump.org/manpages/pcap-filter.7.html
