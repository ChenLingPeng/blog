---
layout: post
title: Distributed Systems Course 6.824 lab 1
category:
tag: [Distributed System]
---



> 本文开始，主要对mit的Distributed Systems课程的实验进行完成。课程网址在[这里](http://nil.csail.mit.edu/6.824/2015/index.html)

- 本章是lab 1的实验

# Part 1：Word Count

第一部分的实验是在给定代码上实现一个wordcount程序，只需要完成 main/wc.go下面的Map和Reduce函数即可。
Map阶段将传入的句子（value）分割成各个单词然后使用提供的KeyValue结构存储到List中，Key为单词，value为1表示单词出现的次数。
Reduce将给每个单词计数，最终得到整个文本的单词计数。

运行命令为`go run wc.go master kjv12.txt sequential`, 也可以直接`sh ./test-wc.sh`运行并检验结果

```
func Map(value string) *list.List {
	f := func(c rune) bool {
		return !unicode.IsLetter(c)
	}
	words := strings.FieldsFunc(value, f)
	stream := list.New()
	for _, word := range words {
		stream.PushBack(mapreduce.KeyValue{Key: word, Value: "1"})
	}
	return stream
}

func Reduce(key string, values *list.List) string {
	count := 0
	for e := values.Front(); e != nil; e = e.Next() {
		c, _ := strconv.Atoi(e.Value.(string))
		count += c
	}
	return strconv.Itoa(count)
}
```

#  Part 2&3: Distributing MapReduce jobs & Handling worker failures

第一部分只是在本地模拟MR实现，这一部分抽象成Master/Client模式运行MR程序，server端主要负责切分作业并下发以及最终结果的收集合并，client负责具体的map/reduce任务。并且，需要处理client端发生错误时的应对措施。

主要实现mapreduce/master.go中的RunMaster方法，具体做法是使用select从registerChannel中得到新注册的worker，并通过rpc给它们分配任务。worker完成分配的任务后master可以继续下发新任务。如果发生错误，则从server端将这个worker排除在可以重复工作的worker外。
任务分两个阶段，map和reduce，map任务下发完后需要先等待所有map任务全部完成后再开始进行reduce任务。
在reduce阶段完全结束后再告知worker端结束工作。

```
func (mr *MapReduce) RunMaster() *list.List {
	// Your code here
	idleWorder := make(chan string)
	mapChan := make(chan int)
	reduceChan := make(chan int)
	for i := 0; i < mr.nMap; i++ {
		go func(mapN int) {
			for {
				var worker string
				success := false
				select {
				case worker = <-mr.registerChannel:
					mr.Workers[worker] = &WorkerInfo{address: worker}
					jobArgs := DoJobArgs{File: mr.file, Operation: Map, JobNumber: mapN, NumOtherPhase: mr.nReduce}
					var reply DoJobReply
					success = call(worker, "Worker.DoJob", jobArgs, &reply)
				case worker = <-idleWorder:
					jobArgs := DoJobArgs{File: mr.file, Operation: Map, JobNumber: mapN, NumOtherPhase: mr.nReduce}
					var reply DoJobReply
					success = call(worker, "Worker.DoJob", jobArgs, &reply)
				}
				if success {
					mapChan <- mapN
					idleWorder <- worker
					return
				} else {
					delete(mr.Workers, worker)
				}
			}
		}(i)
	}
	for i := 0; i < mr.nMap; i++ {
		<-mapChan
	}
	for i := 0; i < mr.nReduce; i++ {
		go func(reduceN int) {
			for {
				var worker string
				success := false
				select {
				case worker = <-mr.registerChannel:
					mr.Workers[worker] = &WorkerInfo{address: worker}
					jobArgs := DoJobArgs{File: mr.file, Operation: Reduce, JobNumber: reduceN, NumOtherPhase: mr.nMap}
					var reply DoJobReply
					success = call(worker, "Worker.DoJob", jobArgs, &reply)
				case worker = <-idleWorder:
					jobArgs := DoJobArgs{File: mr.file, Operation: Reduce, JobNumber: reduceN, NumOtherPhase: mr.nMap}
					var reply DoJobReply
					success = call(worker, "Worker.DoJob", jobArgs, &reply)
				}
				if success {
					reduceChan <- reduceN
					idleWorder <- worker
					return
				} else {
					delete(mr.Workers, worker)
				}
			}
		}(i)
	}
	fmt.Println("waiting for reduce done!")
	for i := 0; i < mr.nReduce; i++ {
		<-reduceChan
	}
	fmt.Println("reduce done with living worker", len(mr.Workers))
	// consume idle workers...
	for i := 0; i < len(mr.Workers); i++ {
		fmt.Println(<-idleWorder)
	}
	return mr.KillWorkers()
}
```

