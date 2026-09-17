# Ontology Generator + ChatBI

对照 [Microsoft Ontology Playground / Fabric IQ Fourth Coffee](https://microsoft.github.io/Ontology-Playground/) 手搓的 Python 实现：

- 输入 **entities + relationships 数据字典**（YAML/JSON）
- 生成 SQLite schema、本体拓展图、样例事实
- HTML Prompt 网站：自然语言 → NL2SQL → 裁剪后的 ontology 子图 + ChatBI facts

默认本体：6 实体、7 关系（Customer / Order / Product / Store / Supplier / Shipment）。

## 运行

```powershell
cd C:\Users\Hennie.Ye\ontology-generator
python -m ontology_agent serve
```

打开 http://127.0.0.1:8765

试一试：

```
customer 最大的销售和最大的 supplier
```

会返回：

1. 按 `totalSpend` 最大的 Customer
2. 对该顾客供货金额最高的 Supplier（Customer → places → Order → contains → Product → sourcedFrom → Supplier）
3. 裁剪后的本体子图
4. 对应 SQL

## CLI

```powershell
python -m ontology_agent generate dictionaries\fourth_coffee.yaml
python -m ontology_agent ask "customer 最大的销售和最大的 supplier"
```

## 换自己的字典

`dictionaries/fourth_coffee.yaml` 的结构即可：`entities[].properties` + `relationships[]`（`from` / `to` / `cardinality`）。  
页面左侧也可粘贴 JSON 后点「从字典生成本体」。

注意：样例种子数据绑定 Fourth Coffee 表结构；换实体名后图和 DDL 会生成，但需要自行补实例数据才能出 ChatBI 数字。
