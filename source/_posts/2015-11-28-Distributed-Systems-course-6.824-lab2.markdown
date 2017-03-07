---
layout: post
title: Distributed Systems Course 6.824 lab 2
category: [Distributed System]
---

> 实验要求在[这里](http://nil.csail.mit.edu/6.824/2015/labs/lab-2.html)

- 本实验分为两部分，首先是实现一个viewservie，控制server视图，使在某一时刻，最多只有一个primary的server提供服务，如果有空闲server，纪录到backup中，一旦primary的server出现异常，backup就会被选为primary继续提供服务。其次是在此基础上实现一个kv存储服务。只有primary的server直接面向client提供Get/Put/Append服务。

# Part A: The Viewservice

这部分主要是控制viewservice的逻辑，使之能过确定一个primary和backup。能成为primary有两种情况，一是viewservice启动时第一个注册的server，或者之前是一个backup且viewservice判断当前primary无效。
viewservice控制view的版本，在一下情况下，view的版本会更新：

1. 一段时间内没有收到p/b的ping
2. p/b中有一个重启了（重启后发送的view version为0，表示重启）。
3. primary为空且存在一个backup server。

但是view变更存在一个前提条件，就是当前的view版本已经被primary认可，即当前版本被primary重新ping过。

# Part B: The primary/backup key/value service

这部分需要在viewservice基础上完成一个kv store service，主要的思想是

1. 只有primary server提供服务。
2. 在Put/Append操作时，需要同步到backup
3. 因为Append本身不满足at-most-once语义，需要在server端加以控制，具体就是纪录下已经操作成功的append操作（由于课程说明，只纪录最近一次即可。）
4. 要处理各种异常情况，如果backup变化，需要从primary完全同步到backup(尝试多次)。如果primary/backup有一个出现错误，client应该知道这种错误并重新发起请求，这时候需要先更新view，重新获取primary。


总的来说，还是挺麻烦的，这部分实验花了挺多时间，主要是在p/b之间的数据同步上，虽然最后给出test case都过了，但是肯定还是会有一些情况没有考虑。