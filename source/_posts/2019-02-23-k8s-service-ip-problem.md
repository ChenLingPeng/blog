---
title: k8s service ip problem
date: 2019-02-23 09:48:00
tags: [network, kubernetes]
---


> 最近在部署山东电力gaiastack环境，现场部署的小伙伴突然遇到紧急问题，发现在容器里面无法通过kubernetes这个service来访问kube-apiserver，导致我们的云盘无法提供正常服务。

> gaiastack是什么？gaiastack是我们组开发的企业级kubernetes容器云管理平台，目前已在公司内外树立了一批标杆客户



在解决问题之前，我们先来看一下涉及到的一些概念。
首先来简单介绍一下kubernetes中service的概念。在kubernetes中，实际提供服务的主体是Pod，每个Pod都有自己的IP地址。由于各种异常，Pod可能发生重启或者迁移，这个时候Pod的IP会发生变化。Service是对一组Pod的网络上的抽象，通过设置labelSelector来对应后端实际的Pod。service对应一个ServiceIP，这个IP是不变的，客户端可以通过访问这个不变的service IP来访问后端提供服务的会发生IP变化的Pod服务。

![kubernetes service](/images/k8s-service.png)

一般来说，service由用户主动创建，kubernetes中有一个controller的组件，会根据用户创建的service中的label Selector来选择相应的Pod，并将其信息写到与service名字同名的endpoint对象中。节点上的kube-proxy通过读取endpoint信息来找到映射关系，维护iptables规则。

```
[KUBE-SERVICES] 
-d 172.24.0.2/32 -p tcp -m tcp --dport 53 -j KUBE-SVC-ERI

[KUBE-SVC-ERI] 
-m statistic --mode random --probability 0.5 -j KUBE-SEP-EME
-j KUBE-SEP-QON

[KUBE-SEP-EME] 
-p tcp -m tcp -j DNAT --to-destination 172.16.103.216:53
```

再来看一下这里遇到问题的名为kubernetes的service。这个service相较于一般的service有一些特殊之处。首先它是由kube-apiserver这个组件自己启动的时候创建的，且这个service没有label selector，它对应的endpoint信息是kube-apiserver自己更新的，会将自己的服务地址写到endpoint中，而不是通过controller去维护这个值。

所以这里有一个问题就是一旦其中某个kube-apiserver挂了，它的endpoint信息还存在，很可能导致服务访问时访问到已经不提供服务的kube-apiserver。
所以在看到这个问题时，首先需要排查是否对应的两个master节点服务都是可用的。telnet之后发现两个apiserver都是可以直接访问的，但是通过service时却不可以。那么问题就可能出在将serviceIP转成实际kube-apiserver的时候。需要进一步检查这个service的iptables规则。如下是现场的小伙伴发来的iptables相关的规则：

![iptables规则](/images/k8s-iptables.png)

可以看到iptables的规则是没问题的，是按照我们希望的方式在配置的。所以这里也不是这个问题。那么这里为什么直接通过机器ip可以但是通过serviceIP转一下就不行呢？突然一想今天现场的同事同步给我了一次环境网络变更，这次变更主要是由于这批机器有两张网卡，业务方今天为了解决网络冲突，删除了主机上的一个网关路由配置，而默认路由走的是另一张我们没有管理和使用的网卡(网段)。这个变更对这里的通信有什么影响呢？就是包的源地址选择！在之前的网络组件开发过程中，我们也遇到过这类由于源地址不是我们想要的源地址而造成的网络故障。linux在构造IP包时，需要填写源地址，那么如何确定这个源地址呢？通常是按照以下规则来的：
1. 如果指定了源地址，直接使用，一般回包时都是这种情况，不存在需要重新选择源地址
2. 如果没有指定，则需要根据目的地址来匹配主机路由规则，路由规则中有一个src选项，可以指定匹配这条路由规则的包的源地址使用src的IP
3. 如果src上也没有指定，则使用路由规则中指定设备上的第一个IP地址作为其源地址
4. 。。。

有了这个怀疑，我们就查看了主机上的路由信息和网卡IP信息，如下图所示：

![route表](/images/route.png)

![网卡地址](/images/addr.png)

结果正如我们所料，当指定目的地址是10.0.0.8时，匹配的路由 `10.0.0.0/24 dev enslf0`，源IP地址被设置为10.0.0.12。
当我们指定的目的地址是172.24.0.1，匹配到了默认路由`default dev enslf1`，此时源地址是10.141.13.182，此时kube-apiserver收到包后无法通过网关往回发，导致无法通信。

解决办法就是根据源地址选择的策略，我们手动配置一下serviceIP网段的路由，指导源地址的选择。这里只需要配置`ip r add 172.24.0.0/13 dev enslf0`，就会选择正确的源IP地址。为了防止重启后丢失这个路由，将其写入crontab即可。

