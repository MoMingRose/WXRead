该项目仅供参考学习，切勿用于其他不合法用途!

欢迎大家针对项目中代码、逻辑等的不足、可优化以及bug，向作者提出建议

# 简单文档记录

[TG通知](https://t.me/mmlg_ql)

> [!TIP]
> 下方是作者使用的环境
>
> 青龙面板版本：`2.17.2`（whyour/qinglong:debian）
>
> 开发环境Python版本: `3.10`

### 2.17.2版本青龙拉库命令-v1-

```shell
ql repo https://github.com/MoMingRose/WXRead.git "read" "" "*" "" "py|yaml"
```

### 2.16.2版本

```shell
ql repo https://github.com/MoMingRose/WXRead.git "read" "" ".*" "master" "py|yaml"
```
### 2.15.4版本

```shell
ql repo https://github.com/MoMingRose/WXRead.git "read" "" "config|exception|schema|script|utils" "master" "py|yaml"
```

### python3依赖

- 必装依赖

```text
httpx
pydantic==1.10.12
colorama
pyyaml
```

- 选装依赖

```text
ujson
```


### 配置环境

个人觉得针对这个项目来说 如果配置env 则会比较杂乱，不容易修改

所以此项目采用`yaml`文件进行配置，具体可参考对应任务的`example.yaml`文件

在项目下的`config`文件夹中，里面有具体的注释

🥤 于 2024.04.03 测试正常
😸 于 2024.04.03 测试正常

如果这个项目让你感到心情愉悦，可以支持一下，点个Start

土豪大佬也可以请作者吃个鸡腿