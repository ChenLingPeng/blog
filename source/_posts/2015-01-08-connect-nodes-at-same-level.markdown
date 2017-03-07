---
layout: post
title: Connect nodes at same level
category: algorithm
tag: [algorithm]
---

> 本题来源于 [GeeksforGeeks](http://www.geeksforgeeks.org/connect-nodes-at-same-level/)

# 题目描述：
> 二叉树有一个节点叫做nextRight，希望将他指向同级右侧邻接节点。

> Write a function to connect all the adjacent nodes at the same level in a binary tree. Structure of the given Binary Tree node is like following. 
Initially, all the nextRight pointers point to garbage values. Your function should set these pointers to point next right for each node.   

```
struct node{
	int data;
    struct node* left;
    struct node* right;
	struct node* nextRight;  
}
```

## 思路一：
> 使用queue进行遍历，并记录节点的level。然后直接往后指就好了。

## 思路二：
> 思路一需要有额外的存储空间，可以用递归的思路精细的构造。  
我们可以层次化的构造，将上面一行处理完，在处理下面一行的时候，用上面一行进行引导，记录当前行L的当前节点（初始为当前行的第一个节点），然后将其孩子进行nextRight的处理。处理的过程是记录下该行(L+1)已经有nextRight，然后当前行(L)去引导这个点向前进。具体看代码。

```
#include <iostream>

using namespace std;

class node
{
public:
	int data;
	class node *left;
	class node *right;
	class node *nextRight;
};

node* newnode(int data) {
	node* n = new node;
	n->data=data;
	n->left=NULL;
	n->right=NULL;
	n->nextRight=NULL;
	return n;
}
void solution(node* root);
void printAllRight(node* first);
int main() {
	node *root = newnode(1);
	root->left = newnode(2);
    root->right = newnode(3);
	root->left->left = newnode(4);
	root->left->right = newnode(5);
	root->right->right=newnode(6);
	root->right->right->left=newnode(7);
	root->right->right->right=newnode(8);
	solution(root);
	printAllRight(root);
	printAllRight(root->left);
	printAllRight(root->left->left);
	printAllRight(root->right->right->left);
}

void solution(node* root) {
	node* first = root;
	node* nextLevelFirst = NULL;//指向下一层第一个节点
	node* nextLevelLast = NULL;//指向下一层最后一个有nextRight的节点
	while(first){
		node* current = first;
		while(current){
			if(current->left){
				if(!nextLevelFirst){
					nextLevelFirst=current->left;
				}
				if(nextLevelLast){
					nextLevelLast->nextRight=current->left;
				}
				nextLevelLast=current->left;
				if(current->right){
					nextLevelLast->nextRight=current->right;
					nextLevelLast=current->right;
				}
			} else if(current->right){
				if(!nextLevelFirst){
					nextLevelFirst=current->right;
				}
				if(nextLevelLast){
					nextLevelLast->nextRight=current->right;
				}
				nextLevelLast=current->right;
			}
			current = current->nextRight;
		}
		first=nextLevelFirst;
		nextLevelFirst=NULL;
		nextLevelLast=NULL;
	}
}


void printAllRight(node* first) {
	while(first){
		cout<<first->data<<"---";
		first = first->nextRight;
	}
	cout<<"NULL"<<endl;
}
```

