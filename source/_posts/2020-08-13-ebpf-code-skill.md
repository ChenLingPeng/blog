---
title: ebpf code skill
date: 2020-08-13 20:15:01
tags: [ebpf, kernel]
---

    本文介绍编写 ebpf 程序时可能遇到的坑或注意事项，持续更新中

0. 最大的原则：不要一次性写太多代码！！！

    每次写少量代码后都需要编译测试，千万不要一次性写太多逻辑。否则一旦代码有问题，导致无法load到内核，非常难定位具体错在哪。ebpf的报错信息实在太坑爹，这也是为什么会有本文的原因

1. ntohs

    ```C
    u16 sport = skb->sport;
    sport = ntohs(sport);

    // 错误写法
    // u16 sport = ntohs(skb->sport);
    ```

    下面错误的写法在加载时会报 'permission deny' 错误。

2. 

从map中lookup出来的指针，不能直接update回去，在ebpf代码中更新值之后不再需要重新update，因为拿到了引用

3. struct初始化问题

    定义结构体
    ```
    #define SERVER_SIDE 0
    struct sock_info {
        u64 ts;
        u32 direct:1,
            flag1:7,
            flag2:8,
            flag3:16;
    } __attribute__((packed));
    ```

    按以下方式初始化结构体会报错
    ```
    struct sock_info info = {
    .ts = 0,
    .direct = SERVER_SIDE,
    };
    ```

    需要先声明 `u64 ts = 0` 然后赋值

4. 字符串拷贝可以使用编译器内置的 `__builtin_memcpy`

5. 关于从kretprobe中获取函数入参

    kretprobe获取函数入参，使用`ctx->bx`
    ```
    int kretprobe__tcp_set_state(structpt_regs*ctx){
    struct sock*sk=(void*)ctx->bx;
    u16 dport = sk->__sk_common.skc_dport;
    dport = ntohs(dport);
    u16 sport=sk->__sk_common.skc_num;
    u32 daddr=sk->__sk_common.skc_daddr;
    u32 saddr=sk->__sk_common.skc_rcv_saddr;
    if(sport == 8087 || dport==8087){
        u32 state=(u32)ctx->cx;
        bpf_trace_printk("sport %d dport %d state %d\n",sport,dport,state);
    }
    return0;
    }
    ```

    但是，目前只能获取第一个参数，第二个参数用ctx->cx无法获取（虽然不报错）

    注：问了社区的人，ctx->bx这种做法也是不保证对的，这里能获取到有一定的lucky成份

6. 获取当前进程cgroup path

    ```
    task = (struct task_struct *)bpf_get_current_task();
    u32 nr_tasks = task->cgroups->nr_tasks;
    char name[100];
    char path[100];
    u32 readn = bpf_probe_read_str(&name, sizeof(name), task->sched_task_group->css.cgroup->kn->name);
    if (task->sched_task_group->css.cgroup->kn->parent) {
    u32 len = bpf_probe_read_str(&path, sizeof(path), task->sched_task_group->css.cgroup->kn->parent->name);
    if (len > 3) {
        if (path[0]=='p' && path[1]=='o'&&path[2]=='d') {
            // this is a pod
        }
    }
    }
    ```

7. 遇到有些struct并没有出自linux标准header定义里，需要自己在代码里伪造一个

    例如上例中的`sched_task_group->css`, 需要自己定义：
    ```
    struct task_group {
        struct cgroup_subsys_state css;
    };
    ```

8. 再谈 kretprobe

    关于获取kretprobe的方式，一般是配合kprobe使用，在kprobe中用pid_tgid作为key来存储信息，在kretprobe中用pid_tgid来取出信息；这里的疑问是，比如在go的GPM调度模型中G(goroutine)是可以跨M调度的，如果当前G在M中执行时，在执行到kprobe存储信息之后，由于时间片已消耗被linux调度器抢占执行其他线程，那么恢复goroutine执行逻辑的时候可能已经跑到别的M上执行了，此时在执行kretprobe的时候，pid_tgid会发生变化。或者还有一种情况，在M重新被调度指挥，go的调度器此时会另一个goroutine来执行，此时如果也触发了kprobe, 相对于再次存储，覆盖了刚才存储的信息。

9. map空间问题

    bcc下bpf map有默认值，有时候需要注意下是否足够，例如我之前用BPF_HASH来记录tcp连接情况，可能默认的10240是不够的
