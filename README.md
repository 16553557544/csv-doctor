# csvfix

CSV 一打开就是一堆乱码，或者中文全变成方块——**问题几乎从来不在文件内容，而在编码。**

这个脚本不猜：先说清楚你的文件到底是什么编码、Excel 为什么读错，再给一个确定的修法。

```
python csvfix.py check 你的文件.csv     # 先诊断，不改文件
python csvfix.py fix   你的文件.csv     # 转成 Excel 认得的编码
```

---

## 那个最经典的症状

**同一个 CSV，WPS 能正常打开，Excel 打开全是乱码。**

这不是文件坏了，是编码的问题：

- 文件里存的是 **GBK**（中文 Windows 的默认编码，很多系统、很多导出工具默认就写这个）
- Excel 打开时按 **UTF-8** 去解码，GBK 字节喂进 UTF-8 解码器 → 中文全乱
- WPS 对编码的猜测宽松得多，它会自动试，所以"看起来正常"

反过来也成立：文件是 UTF-8 但没带 BOM，个别老版本 Excel 会当成系统默认编码读，一样乱。

**这两种情况 csvfix 都能一次判出来。**

---

## 真实测试

```
$ python3 csvfix.py check gbk.csv
文件: gbk.csv  (69 字节)
开头字节: b'\xd0\xd5\xc3\xfb,\xb2\xbf\xc3'
判定编码: GBK / GB18030（中文 Windows 的默认编码）
行数: 3  分隔符: 逗号

**Excel 打开会乱码，WPS 通常能正常显示**——这就是最经典的那个症状。
因为 WPS 会自动猜测编码，Excel 只会按 UTF-8 或系统默认去解。
```

```
$ python3 csvfix.py check utf8bom.csv
判定编码: UTF-8 带 BOM

已经是 UTF-8 带 BOM，Excel / WPS 都正常，不用改。
```

修复：

```
$ python3 csvfix.py fix gbk.csv -o fixed.csv
已转成 UTF-8（带 BOM），输出: fixed.csv
```

修完文件前三个字节是 `EF BB BF`（BOM），Excel 双击就能正确显示中文。

---

## 用法

| 命令 | 作用 |
|---|---|
| `python csvfix.py check <文件>` | 诊断编码、行数、分隔符、Excel 会不会乱，不改文件 |
| `python csvfix.py fix <文件>` | 转成 UTF-8 带 BOM，默认输出 `<原名>-utf8.csv` |
| `python csvfix.py fix <文件> --no-bom` | 转成 UTF-8 不带 BOM（给程序读用，避免多出一个 `\ufeff`） |
| `python csvfix.py fix <文件> --inplace` | 直接覆盖原文件 |

零依赖，Python 3.6+ 直接跑。

---

## 为什么要专门判断 GBK 而不是直接转

因为"能解码"和"解对了"是两件事。GBK、Big5、Shift-JIS、Windows-1252 的字节范围大量重叠，随便一种都能把一串字节"解码成功"，但可能是垃圾。

csvfix 的做法是先看 BOM，再看 UTF-8 能不能干净解出来，最后才对 GBK 候选做**常用字打分**——解出来的是"姓名""部门""金额"这类正常词才认，解出一堆生僻字就不认。

Windows-1252 放在最后，因为它在任何字节上都能"解码成功"，判断力最弱，不该抢在前面。

---

## 已知局限

- 只处理**编码**问题，不修**内容**问题。如果文件里本来就有 `锟斤拷` 这种已经转换失败、信息丢失的字符，那是不可逆的，只能从原始来源重新导出。
- 不处理超大文件（整个读进内存，几百 MB 的 CSV 会吃内存）。
- 分隔符只做逗号 / 制表符 / 分号的初步判断，不做完整 CSV 解析——它转的是字节编码，不是表格结构。

---

## 什么时候用不上

如果乱码出现在**压缩包解出来的文件名**上，那属于另一个问题，用 `zip-name-fixer`。

---

## 许可

MIT
