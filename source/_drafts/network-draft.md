---
title: network draft
tags:
---

> 介绍一些常见的名词

1. [hairpin](https://supportforums.cisco.com/discussion/11650736/hairpin)

	hairpin一般是交换机的一个功能。通常，一次arp请求查询ip对应的mac地址时，交换机会将该请求发给源端口以外的其他所有端口。如果需要将该请求发回源端口查询，就需要交换机开启hairpin模式。[这篇文档](http://blog.csdn.net/dog250/article/details/45788279)中提到了hairpin。

2. [promiscuous mode, 混杂模式](https://en.wikipedia.org/wiki/Promiscuous_mode)

	在混杂模式下，网卡会接受那些目的地址并非本卡地址的包

3. [proxy arp](https://en.wikipedia.org/wiki/Proxy_ARP)

	代理ARP，主要是一个设备应到目的地址不是它的ARP请求。例如路由开启代理ARP，由于子网A所在的路由器知道如何将请求发送给主机B，子网A中的主机发送ARP获取子网B的主机的MAC地址时，路由器会将自己的MAC地址告诉主机A，这样主机A的arp表中主机B的IP对应的MAC地址其实就是路由器的地址。可以看[这个例子](http://www.cisco.com/c/zh_cn/support/docs/ip/dynamic-address-allocation-resolution/13718-5.html)