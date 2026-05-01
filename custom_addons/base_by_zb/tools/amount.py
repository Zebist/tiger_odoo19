# -*- coding: utf-8 -*-
"""通用金额工具方法。"""


def amount_to_chinese_upper(amount):
    """将金额转中文大写（人民币格式：元/角/分）。

    仅用于展示与文档预填，非会计核算；简化实现满足合同 / offer 模板场景。
    """
    cn_num = "零壹贰叁肆伍陆柒捌玖"
    cn_unit = ["", "拾", "佰", "仟"]
    cn_group = ["", "万", "亿", "兆"]
    amount = round(float(amount or 0.0), 2)
    if amount == 0:
        return "零元整"
    sign = "负" if amount < 0 else ""
    amount = abs(amount)
    integer = int(amount)
    fraction = int(round((amount - integer) * 100))
    jiao = fraction // 10
    fen = fraction % 10

    def _four_to_cn(n):
        s = ""
        zero = False
        for i in range(4):
            d = n % 10
            if d == 0:
                if not zero and s:
                    s = cn_num[0] + s
                zero = True
            else:
                s = cn_num[d] + cn_unit[i] + s
                zero = False
            n //= 10
        return s.strip(cn_num[0])

    groups = []
    g_idx = 0
    while integer > 0:
        part = integer % 10000
        if part:
            part_cn = _four_to_cn(part)
            if part_cn:
                groups.insert(0, part_cn + cn_group[g_idx])
        else:
            groups.insert(0, "")
        integer //= 10000
        g_idx += 1

    int_cn = "".join([g for g in groups if g])
    int_cn = int_cn.replace("零零", "零")
    int_cn = int_cn.rstrip("零")
    int_cn = int_cn or cn_num[0]
    result = sign + int_cn + "元"

    if jiao == 0 and fen == 0:
        return result + "整"
    if jiao:
        result += cn_num[jiao] + "角"
    elif fen:
        result += "零"
    if fen:
        result += cn_num[fen] + "分"
    return result
