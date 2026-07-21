# Font combiner

2つのTrueTypeフォントを組み合わせます。Font BにFont Aから指定したUnicodeグリフアウトラインをインポートします。

## 使い方

入力フォントを用意し、次のラッパーを実行します。`FONT_A` と `FONT_B` は必須です。

プロポーショナル版の出力先だけ変更する場合は `PROPORTIONAL_OUTPUT` を指定します。

```sh
FONT_A=fonts/Display.ttf FONT_B=fonts/Text.ttf \
  OUTPUT=dist/Combined.ttf PROPORTIONAL_OUTPUT=dist/Combined-Proportional.ttf ./make.sh
```

デフォルトではFont Aの全cmapをインポートします。採用範囲を制限する場合は、`UNICODE_RANGES` に名前付きレンジや16進数のコードポイント・範囲を指定します（カンマ区切り）。

```sh
FONT_A=fonts/Source.ttf FONT_B=fonts/Base.ttf \
  UNICODE_RANGES=hiragana,katakana,jis_level_1,4e00-4fff \
  OUTPUT=dist/custom.ttf ./make.sh
```

FontTools をインストールし、フォントファイルを用意します。

```sh
python3 -m pip install -r requirements.txt
python3 scripts/merge_fonts.py \
  --font-a fonts/Japanese.ttf \
  --font-b fonts/Latin.ttf \
  --range hiragana,katakana --range jis_level_1,4e00-4fff \
  --output dist/combined.ttf
```

範囲指定がない場合はFont Aに存在する全Unicodeコードポイントを対象にします。Font Bに同じコードポイントがある場合はそのグリフをFont Aのアウトラインへ置換し、ない場合はFont Aのグリフを追加します。

利用できる名前付きレンジは次の通りです。

- 日本語: `japanese`、`hiragana`、`katakana`、`kana`、`kanji`、`jis_level_1`、`jis_level_2`
- 欧文: `ascii`、`latin`、`latin_1`、`latin_extended`、`greek`、`cyrillic`
- 数字・記号: `numbers`、`punctuation`、`symbols`、`math`、`arrows`、`currency`、`box_drawing`、`dingbats`
- 表示用: `fullwidth`、`halfwidth`、`emoji`

`cjk` は `kanji`、`digits` は `numbers`、`latin1` は `latin_1`、`latin-ext` は `latin_extended` の別名です。`kanji` はCJK統合漢字全体、`jis_level_1` と `jis_level_2` はJIS X 0208の第1・第2水準漢字を表します。16進値は `3040-309f`、`U+3040-U+309F`、`0x3040` の形式を使えます。

## 制限

このスクリプトは通常のUnicode cmapを持つ静的なTrueType `glyf` フォント（TTF）を対象にしています。Font Bのメトリクス・レイアウトをベースにし、Font Aの選択グリフのアウトラインを反映します。CFF/OTF、可変フォント、カラーグリフ、複雑な独自拡張テーブルは対象外です。
