---
layout: post
title: Sort an array according to the order defined by another array
category: algorithm
tag: [algorithm]
---

> 本题来源于 [GeeksforGeeks](http://www.geeksforgeeks.org/sort-array-according-order-defined-another-array/)


# 题目描述：
> 给出arr1 arr2两个数组，arr2确定了arr1中的数字的顺序大小，如果arr1中有没有存在arr2的数，则是自然顺序大小。目标是对arr1进行排序。

> Given two arrays A1[] and A2[], sort A1 in such a way that the relative order among the elements will be same as those are in A2. For the elements not present in A2, append them at last in sorted order.  
Input:  
A1[] = {2, 1, 2, 5, 7, 1, 9, 3, 6, 8, 8}  
A2[] = {2, 1, 8, 3}  
Output:   
A1[] = {2, 2, 1, 1, 8, 8, 3, 5, 6, 7, 9}  
The code should handle all cases like number of elements in A2[] may be more or less compared to A1[]. A2[] may have some elements which may not be there in A1[] and vice versa is also possible.

## 思路一：
> 先对arr1进行排序，然后遍历arr2，在排序后的arr1中二分查找元素并加入到结果数组中，并标记已经访问过的点。剩余点再进行遍历放到结果数组中。

## 思路二：
> 使用二叉平衡查找树对arr1进行建树（相同数字标记个数），然后遍历arr2进行查找，并标记已经获取过的点。最后前缀搜索拿出没有访问过的点。

## 思路三：
> 使用Hash对arr1进行计数hash，用arr2去hash中查找，并移除。对剩余数进行排序。

## 思路四：
> 自定义比较函数，然后进行排序。


下面实现了思路四

```
#include <iostream>
#include <map>
#include <algorithm>

using namespace std;
void solution4(int arr1[], int m, int arr2[], int n);
int main(){
	int arr1[] = {2, 1, 2, 5, 7, 1, 9, 3, 6, 8, 8};
	int arr2[] = {2, 1, 8, 3};
	solution4(arr1, 11, arr2, 4);
	return 0;
}

map<int, int> indMap;

bool comparator(int i, int j);
void printArray(int arr[], int n);
void solution4(int arr1[], int m, int arr2[], int n) {
	for(int i=0;i<n;i++){
		indMap[arr2[i]]=i;
	}
	sort(arr1, arr1+m, comparator);
	printArray(arr1,m);
}

void printArray(int arr[], int n)
{
    for (int i=0; i<n; i++)
    cout << arr[i] << " ";
	cout << endl;
}

bool comparator(int i, int j) {
	map<int,int>::iterator it1;
	map<int,int>::iterator it2;
	it1 = indMap.find(i);
	it2 = indMap.find(j);
	if(it1 != indMap.end() && it2 != indMap.end()){
		return it1->second < it2->second;
	} else if(it1 != indMap.end()){
		return true;
	} else if(it2 != indMap.end()){
		return false;
	} else {
		return i<j;
	}
}
```

