# 許可取りくん

<img src="assets/icon/icon.png" width="96" alt="許可取りくんのアイコン">

アプリ開発で必要になる「素材の使用許可」「名称の使用確認」などの依頼メールを、
登録した宛先ごとに AI（Claude）が個別に作成し、確認・編集してから 1 通ずつ送信できる Windows アプリです。
Thunderbird などのメールソフトとは独立して動作します（同じメールアカウントを IMAP/SMTP で直接使います）。

## できること（v0.1 / 最小版）

- **宛先の登録**：名前・所属・敬称・関係性・メモ。メモの内容が文面の個別化に使われます。
- **ジャンル選択**：素材・画像／楽曲／名称・商標／二次利用／データ・API／掲載依頼／協業 など。ジャンルごとの「押さえるポイント」は編集・追加できます。
- **AI で個別作成**：チェックした宛先ごとに別々の文面を作成し、タブで確認・編集できます。不足情報は `【要確認：○○】` として残り、残っている間は送信できません。
- **個別送信**：1 通に 1 宛先で順番に送信します（送信間隔は設定可能）。送ったメールは「送信済み」フォルダにも保存されるので、Thunderbird からも見えます。
- **テスト送信**：表示中の下書きを自分宛てに送って、見え方を確認できます。
- **送信履歴**：送信したメールの一覧（Message-ID も記録しており、次の段階で返信の紐付けに使います）。

## エディション

| | 自分用版 | 販売版 |
|---|---|---|
| Claude Code 経由（今の Claude プランの利用枠） | ○（既定） | ×（コード自体を含めない） |
| Claude API（API キー・従量課金） | ○ | ○ |

- ソースから起動した場合は自分用版になります。
- 販売版の動作を試すには、環境変数 `MAILASSIST_EDITION=commercial` を設定して起動します。
- 配布用の exe は `build\build_commercial.bat` で作ります（`mailassist/ai/cli_backend.py` を除外してビルドします）。

## Windows でのセットアップ

1. [Python 3.11 以上](https://www.python.org/downloads/) をインストールします（「Add python.exe to PATH」にチェック）。
2. このフォルダの `setup_windows.bat` をダブルクリックします。
3. `start.bat` をダブルクリックして起動します。

### Claude Code 経由で使う場合（自分用版）

Claude Code をインストールして、一度ログインしておきます。

```bash
npm install -g @anthropic-ai/claude-code
```

```bash
claude
```

起動後にログインを済ませたら終了して構いません。アプリが自動で `claude` を見つけます。見つからない場合は、設定画面で場所を指定してください。

### 初回設定（メニュー「設定」）

- **メールアカウント**（エックスサーバーの例）
  - SMTP：サーバー `sv○○○○.xserver.jp`、ポート `465`、暗号化 `SSL`、ユーザー名 `info@shirakawaroom.com`
  - IMAP：サーバー `sv○○○○.xserver.jp`、ポート `993`
  - サーバー名はサーバーパネル →「メールアカウント設定」→「メールソフト設定」で確認できます。
  - 「接続テスト」で確認できます。
- **差出人・署名**
- **AI 接続**：Claude Code 経由（既定）か Claude API を選びます。

パスワードと API キーは Windows の資格情報マネージャーに保存されます。その他のデータは `%APPDATA%\KyokaToriKun\data.sqlite3` に保存されます。

## exe の作成

- 自分用：`build\build_personal.bat` → `dist\KyokaToriKun-Personal\KyokaToriKun-Personal.exe`
- 販売用：`build\build_commercial.bat` → `dist\KyokaToriKun\KyokaToriKun.exe`

## 今後の予定

- **フェーズ 2**：受信メールの表示（IMAP）、送ったメールへの返信の紐付け、返信文の自動作成（`mailassist/ai/prompts.py` の `build_reply_prompt` は用意済み）
- アプリ情報のプリセット保存（複数のアプリを切り替え）
- 販売に向けて：ライセンスキー、利用規約・プライバシーポリシー、コード署名

## アイコン

`assets/icon/icon.svg` が元データです（はんこの「可」の文字は日本語フォントで描画）。
変更したら次のコマンドで `icon.png` / `icon_512.png` / `icon.ico` を作り直します。

```bash
python tools/make_icon.py
```

`assets/icon/variants/` には検討した別案（B はんこくん / C チェックくん）を置いています。

## 開発者向け

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest tests
```

構成：

```
mailassist/
  ai/            AI 接続（api_backend.py / cli_backend.py）とプロンプト（prompts.py）
  mail/sender.py SMTP 送信・IMAP 送信済み保存
  ui/            画面（作成・宛先・ジャンル・送信履歴・設定）
  db.py          SQLite 保存
  resources.py   アイコン等の同梱ファイルの場所
  edition.py     自分用版／販売版の判定
```
