#!/usr/bin/python
#
# This is a Hello World example that formats output as fields.

from bcc import BPF
from bcc.utils import printb
import time

# define BPF program
prog = """
#define KBUILD_MODNAME "foo"
#include <net/sock.h>
#include <linux/skbuff.h>
#include <linux/skmsg.h>
#include <linux/tcp.h>

static struct tcphdr *skb_to_tcphdr(const struct sk_buff *skb)
{
    // unstable API. verify logic in tcp_hdr() -> skb_transport_header().
    return (struct tcphdr *)(skb->head + skb->transport_header);
}

int hello_bpf_recv(struct pt_regs *ctx) {
    struct sock *sk = (struct sock *)PT_REGS_PARM1(ctx);
    struct sk_psock *psock;
    u32 l = sk->sk_receive_queue.qlen;
    bpf_trace_printk("Hello, sk_receive_queue len is %d!\\n", l);
    return 0;
}

int hellp_tcp_data_queue(struct pt_regs *ctx) {
    struct sk_buff *skb = (struct sk_buff *)PT_REGS_PARM2(ctx);
    u16 sport = 0, dport = 0;
    struct tcphdr *tcp = skb_to_tcphdr(skb);
    sport = tcp->source;
    dport = tcp->dest;
    sport = ntohs(sport);
    dport = ntohs(dport);
    if (sport == 8080 || dport == 8080) {
        u8 tcpflags = ((u_int8_t *)tcp)[13];
        u32 seq = tcp->seq;
        seq = ntohl(seq);
        bpf_trace_printk("tcp_data_queue for %d, seq %u\\n",dport, seq);
        if (tcpflags & 0x01) {
            bpf_trace_printk("tcp_data_queue get fin\\n");
        }
        if (tcpflags & 0x02) {
            bpf_trace_printk("tcp_data_queue get syn\\n");
        }
        if (tcpflags & 0x10) {
            bpf_trace_printk("tcp_data_queue get ack\\n");
        }
    }
    return 0;
}


"""

# load BPF program
b = BPF(text=prog)
b.attach_kprobe(event="tcp_bpf_recvmsg", fn_name="hello_bpf_recv")
b.attach_kprobe(event="tcp_data_queue", fn_name="hellp_tcp_data_queue")

# header
print("%-18s %-16s %-6s %s" % ("TIME(s)", "COMM", "PID", "MESSAGE"))

# format output
while 1:
    try:
        time.sleep(100)
    except ValueError:
        continue
    except KeyboardInterrupt:
        exit()
    print("waiting")

