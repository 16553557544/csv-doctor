#!/usr/bin/env python3
"""csvfix - 诊断并修复 CSV 里"中文变乱码 / Excel 打开一堆方块"的问题。

它不猜、不硬转，先说清楚这个文件到底是什么编码、Excel 为什么会乱，
再给一个确定的修法：统一转成 Excel 认得的 UTF-8（带 BOM）。

用法:
    python csvfix.py check <文件.csv>              诊断，不改文件
    python csvfix.py fix   <文件.csv> [-o 新文件]   转成 UTF-8(带 BOM)
    python csvfix.py fix   <文件.csv> --no-bom     转成 UTF-8(不带 BOM)
    python csvfix.py fix   <文件.csv> --inplace    直接覆盖
"""

import argparse
import io
import os
import sys

BOMS = {
    b"\xef\xbb\xbf": ("utf-8-sig", "UTF-8 带 BOM"),
    b"\xff\xfe\x00\x00": ("utf-32", "UTF-32 LE"),
    b"\x00\x00\xfe\xff": ("utf-32", "UTF-32 BE"),
    b"\xff\xfe": ("utf-16", "UTF-16 LE"),
    b"\xfe\xff": ("utf-16", "UTF-16 BE"),
}

# 判定 GBK 时用到的常用字，和 zipfix 同一套思路：光"能解码"不算数，解出常用字才算
COMMON = set("的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主"
             "发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里"
             "如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些"
             "然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或"
             "但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展"
             "五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将"
             "组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处书面测试验证"
             "名称日期金额数量价格备注描述类型状态时间编号序号单位部门客户产品订单")


def looks_textual(text):
    """解出来的字符串像不像正常内容。"""
    good = 0
    bad = 0
    sample = text[:5000]
    for ch in sample:
        if ch in COMMON:
            good += 4
        elif 0x4E00 <= ord(ch) <= 0x9FFF:
            good += 1
        elif ord(ch) < 0x20 and ch not in "\r\n\t":
            bad += 6
        elif 0xE000 <= ord(ch) <= 0xF8FF:
            bad += 6
    return good - bad


def detect(data):
    """返回 (编码名, 人类可读说明, 解码后的文本 或 None)。"""
    for bom, (enc, label) in BOMS.items():
        if data.startswith(bom):
            try:
                return enc, label, data.decode(enc)
            except UnicodeDecodeError:
                pass

    try:
        text = data.decode("utf-8")
        return "utf-8", "UTF-8（无 BOM）", text
    except UnicodeDecodeError:
        pass

    try:
        text = data.decode("gb18030")
        s = looks_textual(text)
        if s > 0:
            return "gb18030", "GBK / GB18030（中文 Windows 的默认编码）", text
    except UnicodeDecodeError:
        pass

    # 最后才考虑西欧编码，因为它在任何字节上都能"解码成功"，判断力最弱
    try:
        text = data.decode("cp1252")
        if looks_textual(text) > 0:
            return "cp1252", "Windows-1252（西欧）", text
    except UnicodeDecodeError:
        pass

    return None, "无法识别（可能是二进制文件，或者多种编码混在一起）", None


def diagnose(path):
    with open(path, "rb") as f:
        data = f.read()

    enc, label, text = detect(data)
    first_bytes = data[:8]

    print("文件: %s  (%d 字节)" % (path, len(data)))
    print("开头字节: %s" % first_bytes)
    print("判定编码: %s" % label)

    if text is None:
        print("\n结论: 这个文件不是纯文本 CSV，脚本不做处理。")
        return 2, None, None

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [l for l in lines if l.strip()]
    head = lines[0] if lines else ""
    delim = ","
    if head.count("\t") > head.count(","):
        delim = "\t"
    elif head.count(";") > head.count(","):
        delim = ";"

    print("行数: %d  分隔符: %s" % (len(lines), {"\t": "制表符", ",": "逗号", ";": "分号"}[delim]))

    # 关键判断：Excel 会不会乱码
    if enc == "utf-8":
        verdict = "Excel / WPS 打开都正常，但注意：这是无 BOM 的 UTF-8，个别老版本 Excel 会认错。"
        need_fix = False
    elif enc == "utf-8-sig":
        verdict = "已经是 UTF-8 带 BOM，Excel / WPS 都正常，不用改。"
        need_fix = False
    elif enc in ("gb18030", "cp1252"):
        verdict = ("**Excel 打开会乱码，WPS 通常能正常显示**——这就是最经典的那个症状。"
                   "因为 WPS 会自动猜测编码，Excel 只会按 UTF-8 或系统默认去解。")
        need_fix = True
    else:
        verdict = "UTF-16 系列，Excel 一般能认，但很多脚本处理会出错，建议统一成 UTF-8。"
        need_fix = True

    print("\n" + verdict)
    return 0, text, (delim, need_fix)


def cmd_check(path):
    code, text, _ = diagnose(path)
    return code


def cmd_fix(path, out, bom, inplace):
    code, text, meta = diagnose(path)
    if text is None:
        return 2

    target = path if inplace else (out or (os.path.splitext(path)[0] + "-utf8.csv"))
    enc_out = "utf-8-sig" if bom else "utf-8"
    with open(target, "w", encoding=enc_out, newline="") as f:
        f.write(text)

    if inplace:
        os.replace(target, path)
        target = path

    print("\n已转成 %s，输出: %s" % ("UTF-8（带 BOM）" if bom else "UTF-8（无 BOM）", target))
    if bom:
        print("带 BOM 是为了让 Excel 双击就能正确认出中文；如果你的程序读它会多出一个 \\ufeff，用 --no-bom。")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="csvfix", description="诊断并修复 CSV 中文乱码。")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="只诊断，不改文件")
    p.add_argument("file")

    p = sub.add_parser("fix", help="转成 UTF-8")
    p.add_argument("file")
    p.add_argument("-o", "--out")
    p.add_argument("--no-bom", action="store_true")
    p.add_argument("--inplace", action="store_true")

    args = ap.parse_args()
    if not os.path.exists(args.file):
        print("找不到文件: %s" % args.file, file=sys.stderr)
        return 2

    if args.cmd == "check":
        return cmd_check(args.file)
    return cmd_fix(args.file, args.out, not args.no_bom, args.inplace)


if __name__ == "__main__":
    sys.exit(main())
