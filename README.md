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

> [!WARNING]
> 请先在当前使用的青龙面板中安装`pydantic`依赖（Python3的）\
> 如果安装失败，那么此项目将不适合你 \
> 或者将青龙转成`debian`版本

### 青龙拉库命令-v1

```shell
ql repo https://github.com/MoMingRose/WXRead.git "read" "" "*" "" "py|yaml"
```

如果不行尝试下方的看看 `2.16.2`版本可以拉取成功

```shell
ql repo https://github.com/MoMingRose/WXRead.git "read" "" ".*" "master" "py|yaml"
```


### python3依赖

```text
httpx
pydantic
colorama
pyyaml
ujson
```

### 配置环境

个人觉得这对这个项目来说 如果配置env 则会比较杂乱，不容易修改

所以此项目采用`yaml`文件进行配置，具体可参考对应任务的`example.yaml`文件

在项目下的`config`文件夹中，里面有具体的注释

🥤阅读于 2024.04.02 测试无误

如果这个项目让你感到心情愉悦，可以支持一下，点个Start

土豪大佬也可以请作者吃个鸡腿