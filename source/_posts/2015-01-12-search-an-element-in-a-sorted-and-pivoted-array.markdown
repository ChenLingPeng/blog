---
layout: post
title: Search an element in a sorted and pivoted array
category: algorithm
tag: [algorithm]
---

> 本题来源于 [GeeksforGeeks](http://www.geeksforgeeks.org/search-an-element-in-a-sorted-and-pivoted-array/)

# 题目描述：

> 给出一个排序过的数组，但是经过了一次反转，现在进行search。

> An element in a sorted array can be found in O(log n) time via binary search. But suppose I rotate the sorted array at some pivot unknown to you beforehand. So for instance, 1 2 3 4 5 might become 3 4 5 1 2. Devise a way to find an element in the rotated array in O(log n) time.

## 解法（无重复）：

> 没有什么技巧，就是思路清晰就好。

> 因为是有序，所以我们每次二分拿到中点的时候，看看哪半段是真正有序的

>> 如果`arr[first]<=arr[mid]`，那么说明前半段是有序，就用前半段的两个边界点判断就可以知道target在前面还是后面；

>> 否则说明后半段是有序的，那么就用后半段边界点比较就可以知道是在前面还是后面。

下面是无重复的代码实现

```
#include <iostream>

using namespace std;

int search(int *arr, int size, int target){
	int first=0, last=size;
	while(first!=last){
		int mid=(first+last)/2;
		if(arr[mid]==target) return mid;
		if(arr[first]<=arr[mid]){
			if(arr[first]<=target && arr[mid]>target){
				last=mid;
			} else {
				first=mid+1;
			}
		} else {
			if(target>arr[mid]&& target<=arr[last-1]){
				first=mid+1;
			} else {
				last=mid;
			}
		}
	}
	return -1;
}

int main(){
	int arr[] = {5,6,1,2,3,4};
	for(int i=0;i<6;i++){
		cout<<search(arr,6,i+1)<<endl;
	}
	return 0;
}
```

## 解法（有重复）：

> 当有重复时，也是依靠边界

>> 分析一下，如果前半段或者后半段的两个边界有一个不同，那么就根据上面算法选择一个段。

>> 如果`arr[first]==arr[mid]`，进而如果`arr[mid]!=arr[last]`，那么就只要搜索后半段就行了，因为前半段比如都是一样的数字。用反证法就可以证明：

>>> 假设前半段不是都相等，那么肯定是先递增到最大值，然后从最小值开始增到`arr[mid]`那么大，后面只能增到或者等于`arr[mid]`，现在知道`arr[last]!=arr[mid]`，那么后面一定增大，那么就会导致`arr[last]>arr[mid]`，也就是`arr[last]>arr[first]`，与题意不符合，所以前半段是一样的，只需要搜索后半段就好了。

>> 如果`arr[first]==arr[mid]`且`arr[mid]==arr[last]`，那么前后都有可能，那么都需要搜索。递归的话就搜两段，非递归就把前后各推进1就好了。

>> 还需要考虑`arr[first]!=arr[mid]`但是`arr[mid]==arr[last]`的情况吗？需要，这时候就只需要查找前半段就好了。

下面是一个非递归版本，递归版本来自[codepad.org/mqkc4I3R](http://codepad.org/mqkc4I3R) 上面有bug，没有考虑最后一种情况，我修改了一下，放到了[这里](http://codepad.org/Qljz60Fl)。

有重复非递归的代码实现：

```
#include <iostream>

using namespace std;

int search2(int *arr, int size, int target){
	int first=0, last=size;
	while(first<=last){
		int mid=(first+last)/2;
		if(arr[mid]==target) return mid;
		if(arr[first]<arr[mid]){
			if(arr[first]<=target && arr[mid]>target){
				last=mid;
			} else {
				first=mid+1;
			}
		} else if(arr[mid]<arr[last-1]) {
			if(target>arr[mid]&& target<=arr[last-1]){
				first=mid+1;
			} else {
				last=mid;
			}
		} else if(arr[first]==arr[mid]){
			if(arr[mid]!=arr[last-1]){
				first=mid+1;
			}else{
				first++;
                last--;
			}
		} else {
			last=mid;
		}
	}
	return -1;
}

int main(){
	int arr[] = {6,1,2,3,4,5,5,5,5,5,5,5,5};
	for(int i=0;i<6;i++){
		cout<<search2(arr,13,i+1)<<endl;
	}
	return 0;
}
```

