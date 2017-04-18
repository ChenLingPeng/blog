---
title: iptables quick start
date: 2017-03-30 17:51:32
tags: [network]
---

# 简介

linux内置了一个强大的防火墙模块，称为iptables。用户通过在用户态操作iptables规则，可以使流量在内核态进行规则的匹配过滤。

Man手册中关于iptables的介绍为用于包过滤和NAT的系统工具。

iptables的规则可以从两个角度看。从功能上看，iptables分为多个已经定义好的table，每个table有自己的作用。从对包的操作流水线来看，iptables又是有各个CHAIN组成的。包在内核中游走的各个阶段分别会进入不同的CHAIN进行规则匹配操作。

iptables包含了预先定义好的5个table: filter, nat, mangle, raw, security. 比较常见的是前3个table。用户无法增加新的table

1. filter: 这是默认用户在没有指定操作table时会操作的table。它包含了内置的INPUT, FORWARD, OUTPUT表。主要用于包过滤
2. nat: 这张表的作用主要是对连接进行NAT，包括SNAT和DNAT。它包含了内置的PREROUTING, OUTPUT, POSTROUTING表。
3. mangle: 主要用于对包内容的修改！例如进行mark！它包含了所有内置的CHAIN

iptables的各个table由各个CHAIN组成，内置了5个CHAIN在包游走的各个阶段使用CHAIN中的规则进行过滤操作。

1. PREROUTING chain: 这个chain在包进入主机且没有在本机进行路由决策之前进行规则匹配。通常可以在这里进行DNAT, 例如访问docker容器
2. INPUT chain: 经过本机路由决策后如果判定包是给本机的，则在包进入用户空间被进程处理之前会进过INPUT chain。
3. FORWARD chain: 经过本机路由决策后发现需要路由到其他地方的，则进入该chain处理
4. OUTPUT chain: 用户空间发出的包在进入内核后首先经过这个chain的处理
5. POSTROUTING chain: 经过路由决策后需要发出去的包会经过该chain，可以在这里进行SNAT

具体的流程如下图所示
![kubelet](/images/iptables-chain.png)

除了内置的5个CHAIN，用户还可以创建自己的CHAIN进行扩展。

# 基本命令

1. `iptables [-t table] {-A|-C|-D} chain rule-specification`
	-A表示在末尾append一条规则
	-C表示check规则存不存在
	-D表示删除一条规则
2. `iptables [-t table] -I chain [rulenum] rule-specification`
	在第rulenum条规则前insert一条规则，默认为1，表示加在最开头

3. `iptables [-t table] -R chain rulenum rule-specification`
	replace规则

4. `iptables [-t table] -D chain rulenum`
	delete一条规则

5. `iptables [-t table] {-F|-L|-Z} [chain [rulenum]] [options...]`
	-L表示list规则
	-F表示清空规则
	-Z表示清空包计数

6. `iptables [-t table] -N chain`
	新建一个chain

7. `iptables [-t table] -X [chain]`
	删除用户定义的chain

8. `iptables [-t table] -P chain target`
	设置默认的policy，target必须是ACCEPT或者DROP

9. `iptables [-t table] -E old-chain-name new-chain-name`
	重命名chain

其中：

```
rule-specification = [matches...] [target]
match = -m matchname [per-match-options]
target = -j targetname [per-target-options]

内置的targetname有ACCEPT和DROP
```

新增规则可以跟上以下参数
```
[!] -p, --protocol protocol 根据协议匹配,tcp, udp, udplite, icmp, icmpv6,esp, ah, sctp, mh
[!] -s, --source address[/mask][,...] 源地址匹配
[!] -d, --destination address[/mask][,...] 目的地址匹配
-m, --match match 根据扩展模块进行匹配，后文说明
-j, --jump target 使用target进行处理，如ACCEPT，DROP，或者其他扩展的target如REJECT，SNAT，DNAT等。也可以进入用户自定义的chain中
-g, --goto chain 与-j类似，区别在于如果从chain回来，则不会继续在当前chain继续往下匹配而是return到上一层
[!] -i, --in-interface name 匹配入口网卡，如果name后面跟上+号，匹配所有前缀
[!] -o, --out-interface name 匹配出口网卡
[!] -f, --fragment 匹配非第一个ipv4分片
-c, --set-counters packets bytes 设置计数
--line-numbers 在列出规则时，可以显示rulenumber
```

以上就是iptables的基本用法了。
核心的iptables主要进行ACCEPT和DROP的工作，如果需要使用高级的功能，需要使用iptables的扩展模块。扩展模块对规则的匹配进行了扩展（使用-m match），对匹配规则的目标作用也进行了扩展，可以进行NAT等工作。

# 扩展

## 匹配扩展

addrtype
	! --src-type type
	! --dst-type type
	type->[LOCAL, BROADCAST, BLACKHOLE, ]

cgroup
	! --cgroup fwid
	fwid 是被 cgroup net-cls 设置的
	例子：iptables -A OUTPUT -p tcp --sport 80 -m cgroup ! --cgroup 1 -j DROP

multiport
	! --sports|dports|ports port[,port|port:port]

set
	[!] --match-set setname flag[,flag]
	--return-nomatch
	匹配ip集合，这个集合可以从ipset命令看到。在calico网络中就用到了这种匹配方式
	例子：iptables -A FORWARD -m set --match-set test src,dst

state
	state [state]
	state->[INVALID,  ESTABLISHED, NEW, RELATED or UNTRACKED]

string
	algo [BM|KMP]
	from [offset]
	to [offset]
	string [str]
	hex-string [str]
	icase

tcp
	! --sport|dport port[:port]
	! --tcp-option number
	! --tcp-flags mask comp  mask为需要检查的flags，comp为需要检查的flags中哪些被设置，flags有[SYN ACK FIN RST URG PSH ALL NONE]. 例如`iptables -A FORWARD -p tcp --tcp-flags SYN,ACK,FIN,RST SYN`
	! --syn 与`--tcp-flags SYN,RST,ACK,FIN SYN`等效
	当指定-p tcp时使用

tcpmss
	mss val[:val]
	匹配tcp的mss范围

tos
	! tos val[/mask]
	! --tos symbol
	匹配tos字段

udp
	--sport|dport port[:port]
	当指定-p udp时使用

## 目标扩展

CONNMARK
	--set-xmark value[/mask]

DNAT [nat,PREROUTING,OUTPUT]
	--to-destination [ip][:port]
	修改目的ip

MARK
	--set-xmark value[/mask]
	--set-mark value[/mask]

MASQUERADE [nat,POSTROUTING]
	--to-ports port
	修改源ip地址, 主要用于主机ip会变化的情况。一般使用SNAT

REDIRECT [nat,PREROUTING,OUTPUT]
	--to-ports port[-port]
	重定向到本机地址如127.0.0.1

REJECT [INPUT, FORWARD and OUTPUT]
	--reject-with type
	type -> [icmp-net-unreachable, icmp-host-unreachable, icmp-port-unreachable, icmp-proto-unreachable, icmp-net-prohibited, icmp-host-prohibited, or icmp-admin-prohibited]
	类似于DROP，但是会像请求方返回一个应答而不是不相应

SNAT [nat, POSTROUTING, INPUT]
	--to-source [ipaddr[-ipaddr]][:port[-port]]

TOS [mangle]
	--set-tos value[/mask]
	--set-tos symbol
	设置tos字段

TRACE
	标记连接，之后每条匹配的rule都会被log

