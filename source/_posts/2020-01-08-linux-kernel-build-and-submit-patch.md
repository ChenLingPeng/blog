---
title: linux kernel build and submit patch
date: 2020-01-08 18:25:13
tags: [kernel]
---


> 最近在写bpf/sockmap的时候发现一个sockhash的内核bug，经过一系列定位后终于找到了问题代码并修复，最后将修复的patch提交到了社区。这是第一次向linux kernel提交代码，在这里记录一下~

# linux内核编译

首先需要准备一下编译环境

`apt-get install git fakeroot build-essential ncurses-dev xz-utils libssl-dev bc flex libelf-dev bison`

接下来获取源码进行修改，如果只是在某个版本修改代码且不提交到linux社区，可以直接从[这里](http://cdn.kernel.org/pub/linux/kernel/)下载源码，这个比git clone会快很多。如果希望代码修改后能反馈到社区，则可以`git clone git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git`获取最新代码

进入linux源码目录后，好需要拷贝一份内核配置文件： `cp /boot/config-5.0.0-36-generic .config`

然后可以通过命令`make menuconfig`在图形化界面选择一些配置项，一般我们直接保存退出就可以了。

接下来进行编译，很简单，直接`make -j $(nproc)`进行多核编译，加快编译速度

编译完成后安装内核模块 `make modules_install`

然后安装内核本身 `make install`

最后还需要更新grub 启动项

```
$ sudo update-initramfs -c -k 5.5.0-rc5
$ sudo update-grub
```

最后的最后reboot重启机器，`uname -r`就可以看到是最新的内核版本了

# 提交patch

1. 新建一个分支 `git checkout -t -b fix_sockhash master`

2. 在新分支上修改代码。

3. 生成commit: git commit -s -v。此时会弹出编辑器，需要编辑commit message。

	commit message需要按照一定的格式，首行需要按照格式`<subsystem>/<sub-subsystem>: <descriptive comment>` 这样在`git log --oneline`的时候看的更清晰
	然后空一行，然后具体描述这个commit做了什么。由于git commit时我们加上了-s参数，所以commit message里可以看到最后有`Signed-off-by` ，也就是作者的签名。如果此path是一个bug-fix, 在此之上最好能附上Fixes tag例如：`Fixes: 604326b41a6fb ("bpf, sockmap: convert to generic sk_msg interface")`

	以下是一个完整的commit message 示例

	```
	    bpf/sockmap: read psock ingress_msg before sk_receive_queue
	    
	    Right now in tcp_bpf_recvmsg, sock read data first from sk_receive_queue
	    if not empty than psock->ingress_msg otherwise. If a FIN packet arrives
	    and there's also some data in psock->ingress_msg, the data in
	    psock->ingress_msg will be purged. It is always happen when request to a
	    HTTP1.0 server like python SimpleHTTPServer since the server send FIN
	    packet after data is sent out.
	    
	    Fixes: 604326b41a6fb ("bpf, sockmap: convert to generic sk_msg interface")
	    Reported-by: Arika Chen <eaglesora@gmail.com>
	    Suggested-by: Arika Chen <eaglesora@gmail.com>
	    Signed-off-by: Lingpeng Chen <forrest0579@gmail.com>
	    Signed-off-by: John Fastabend <john.fastabend@gmail.com>
	```

4. 然后使用脚本生成patch `git format-patch master`，或者 `git format-patch HEAD~<number of commits to convert to patches>` 。

5. 检查patch是否有问题并修复： `./scripts/checkpatch.pl 0001-xxx.patch`。没啥问题就可以准备发邮件给社区review了。

6. 接下来就是发送邮件给社区，建议使用 `git send-email` 功能来发送(需要安装git-email `apt install git-email -y`)

	首先需要配置一下email的配置信息，编辑`~/.gitconfig`输入相关邮箱信息，例如gmail的配置如下：
	```
	$ cat ~/.gitconfig:
	[user]
		name = Lingpeng Chen
		email = myemail@gmail.com

	[sendemail]
		from = Lingpeng Chen <myemail@gmail.com>
		smtpserver = smtp.gmail.com
		smtpuser = myemail@gmail.com
		smtpencryption = tls
		smtppass = mypassword
		chainreplyto = false
		smtpserverport = 587
	```

	这里需要设置smtppass，google账号一般开启了`2-Step 验证`，所以直接使用账号的密码可能会发送失败，此时需要进入 `account->security->app-passwords`里面创建一个新的[应用密码](https://myaccount.google.com/apppasswords)。

	配置完后可以发送邮件 `git send-email --to "forrest0579 <forrest0579@gmail.com>" --cc "lingpeng chen <cc@example.com>" 0001-xxx.patch` 可以先往自己的邮箱里面发送看看效果。

	如果没啥问题，我们再往社区发。这里需要给相关的maintainer和一些邮件组发，可以通过脚本来获取，例如：

	```
	$ ./scripts/get_maintainer.pl 0001-bpf-sockmap-read-psock-ingress_msg-before-sk_receive.patch 
	Eric Dumazet <edumazet@google.com> (maintainer:NETWORKING [TCP])
	John Fastabend <john.fastabend@gmail.com> (maintainer:L7 BPF FRAMEWORK,blamed_fixes:1/1=100%)
	Daniel Borkmann <daniel@iogearbox.net> (maintainer:L7 BPF FRAMEWORK,blamed_fixes:1/1=100%)
	"David S. Miller" <davem@davemloft.net> (maintainer:NETWORKING [IPv4/IPv6])
	Alexey Kuznetsov <kuznet@ms2.inr.ac.ru> (maintainer:NETWORKING [IPv4/IPv6])
	Hideaki YOSHIFUJI <yoshfuji@linux-ipv6.org> (maintainer:NETWORKING [IPv4/IPv6])
	Alexei Starovoitov <ast@kernel.org> (supporter:BPF (Safe dynamic programs and tools),blamed_fixes:1/1=100%)
	Martin KaFai Lau <kafai@fb.com> (reviewer:BPF (Safe dynamic programs and tools))
	Song Liu <songliubraving@fb.com> (reviewer:BPF (Safe dynamic programs and tools))
	Yonghong Song <yhs@fb.com> (reviewer:BPF (Safe dynamic programs and tools))
	Andrii Nakryiko <andriin@fb.com> (reviewer:BPF (Safe dynamic programs and tools))
	netdev@vger.kernel.org (open list:NETWORKING [TCP])
	bpf@vger.kernel.org (open list:L7 BPF FRAMEWORK)
	linux-kernel@vger.kernel.org (open list)
	```

	挑选一些人作为收件对象然后发送邮件。

7. 更新patch
	社区的人review之后可能会给出一些意见，修改后还可以使用send-email来回复。此时需要使用`--in-reply-to`来指定回复哪封邮件，邮件的ID可以在邮箱里查看邮件信息看到。例如gmail里可以通过 **显示原始邮件** 得到邮件ID。另外，更新的patch可以使用 `git format-patch -v2`来指定更新的版本号，方便大家review。


最后，http://vger.kernel.org/vger-lists.html 这个网址可以看到各个子系统的邮件组信息。发送完后这里会显示你新发的邮件


# 参考

1. https://www.cyberciti.biz/tips/compiling-linux-kernel-26.html
2. https://www.kernel.org/doc/html/latest/process/submitting-patches.html
3. http://nickdesaulniers.github.io/blog/2017/05/16/submitting-your-first-patch-to-the-linux-kernel-and-responding-to-feedback/
