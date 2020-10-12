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
    ```C
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
    ```C
    struct sock_info info = {
    .ts = 0,
    .direct = SERVER_SIDE,
    };
    ```

    需要先声明 `u64 ts = 0` 然后赋值

4. 字符串拷贝可以使用编译器内置的 `__builtin_memcpy`

5. 关于从kretprobe中获取函数入参

    kretprobe获取函数入参，使用`ctx->bx`
    ```C
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

    ```C
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

10. gobpf库读取percpu map问题
    
    目前gobpf库使用Get/GetP读取map value时，当map类型是percpu类型时，无法完成取出每个cpu对应的值，需要做相应改变，对应的[PR](https://github.com/iovisor/gobpf/pull/254/files)

11. 可以使用`lock_xadd`来解决并发写问题，不过如果可能的话尽量使用 percpu 相关的map来进行计数等操作。

    `lock_xadd`其实也是调用的`__sync_fetch_and_add`

12. linux版本相关的条件编译 `#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 14, 0)`

13. 有限的for循环

    ebpf本身不允许循环的存在，因为会被判定为可能无法及时退出，影响内核执行效率。不过我们如果可以预见到循环将在有限次循环之后退出，可以使用`#pragma unroll`来在编译期间展开for循环，通过bpf的verify组件。当然，循环的次数是有限的，因为bpf本身代码指令的数量有限(4096)

    ```C
    static __inline int is_prefix(char *prefix, char *str)
    {
        int i;
        #pragma unroll
        for (i = 0; i < MAX_PATH_PREF_SIZE; prefix++, str++, i++) {
            if (!*prefix)
                return 1;
            if (*prefix != *str) {
                return 0;
            }
        }

        // prefix is too long
        return 0;
    }
    ```

14. 判断是不是创建了一个容器(pid_namespace)

    ```C
    static __always_inline u32 get_task_ns_pid(struct task_struct *task)
    {
    #if LINUX_VERSION_CODE < KERNEL_VERSION(4, 19, 0)
        // kernel 4.14-4.18:
        return task->pids[PIDTYPE_PID].pid->numbers[task->nsproxy->pid_ns_for_children->level].nr;
    #else
        // kernel 4.19 onwards:
        return task->thread_pid->numbers[task->nsproxy->pid_ns_for_children->level].nr;
    #endif
    }
    ```

    可以通过判断`get_task_ns_pid`是否是1来判断是否新的进程是创建在容器里的, trace点在系统调用`execve`和`execveat`, 进程退出点在`do_exit`

15. 获取参数问题

    有2中方式可以获取kprobe触发函数的参数，一个是使用`PT_REGS_PARMN`的形式来获取，另一个是在你的kprobe hook函数上直接申明。对于复杂的数据结构，建议使用第2中方式直接在函数参数中声明，否则可能读不出来，load BPF程序的时候会报错。[issue3086](https://github.com/iovisor/bcc/issues/3086)

16. BPF_PERCPU_HASH

    bcc目前没有定义`BPF_PERCPU_HASH`这个宏，需要使用的话可以用 `BPF_TABLE("percpu_hash", _key_type, _leaf_type, _name, _size)` 来定义

17. stack空间限制512byte

    一个bpf程序不能申请太多的栈空间，目前限制512B，多了就会报错：`Looks like the BPF stack limit of 512 bytes is exceeded.`。
    例如在程序中申请了两个数组`char arr1[256];char arr2[256];`程序就会报错了

18. bpf程序需要特权

    加载bpf程序需要一定的特权，比如使用bpf syscall需要SYS_ADMIN权限。所以我们在docker中跑的时候一般使用`--privileged`。如果在k8s环境，有些环境可能并不能直接使用privileged，此时需要使用capabilities来给bpf程序必要的权限。测试会发现，只添加SYS_ADMIN权限还是不够的，运行时会报类似`could not open bpf map: cstat, error: Operation not permitted`的错误。strace一下系统调用可以看到，权限问题是在调用prlimit64时出现的。
    ```
    prlimit64(0, RLIMIT_MEMLOCK, NULL, {rlim_cur=64*1024, rlim_max=64*1024}) = 0
    prlimit64(0, RLIMIT_MEMLOCK, {rlim_cur=RLIM64_INFINITY, rlim_max=RLIM64_INFINITY}, NULL) = -1 EPERM (Operation not permitted)
    ```
    查阅资料可知，要设置memlock，除了SYS_ADMIN，还需要SYS_RESOURCE
