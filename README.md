# PDFからnote制作 — Codex Plugin

PDFの内容を丁寧に反映したnote記事、本文スライド、サムネイル1案を作るCodexプラグインです。

## Install

```bash
codex plugin marketplace add fuuuuuuma/pdf-to-note
codex plugin add pdf-to-note@pdf-to-note
```

確認には `codex plugin marketplace list` と `codex plugin list` を使います。インストール後、新しいCodexチャットで `$pdf-to-note` とPDFを指定してください。

## 動作と前提

- 公開は利用者本人がその実行で明示した場合だけ行います。明示がなければ下書き保存までです。
- YouTubeとXへの投稿は行いません。
- noteのブラウザ操作には、noteへログインしたCodexアプリ内ブラウザが必要です。
- サムネイル生成には画像生成機能が必要です。`sumnessy-team` などの追加Skillは、利用者が指定し、環境にある場合に使います。なくても同梱の画像制作基準で進めます。
- PDFの全文抽出・図版レンダリング用スクリプトにはPython 3とPoppler（`pdfinfo`、`pdftotext`、`pdftoppm`）が必要です。

プラグインには記事編集の参考資料とPDF処理・保存内容検証用スクリプトを同梱しています。
