---
title: network draft
tags:
---

> 介绍一些常见的名词

1. [hairpin]

	hairpin一般是交换机的一个功能。通常，一次arp请求查询ip对应的mac地址时，交换机会将该请求发给源端口以外的其他所有端口。如果需要将该请求发回源端口查询，就需要交换机开启hairpin模式。[这篇文档](http://blog.csdn.net/dog250/article/details/45788279)中提到了hairpin。

2. [promiscuous mode, 混杂模式](https://en.wikipedia.org/wiki/Promiscuous_mode)

	在混杂模式下，网卡会接受那些目的地址并非本卡地址的包
