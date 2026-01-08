"""CLI ツール - コマンドラインから検索・アップロード"""

import click
import requests
from pathlib import Path

API_URL = "http://localhost:8000"


def print_results(results: list) -> None:
    """検索結果を表示"""
    for r in results:
        click.echo("-" * 60)
        click.echo(f"書籍: {Path(r['file']).name}")
        click.echo(f"ページ: {r['page'] + 1}")
        click.echo(f"スコア: {r['score']:.3f}")
        click.echo(f"テキスト: {r['text'][:200]}...")
        click.echo()


@click.group()
@click.option('--api-url', default=API_URL, envvar='KUGUTSUSHI_API_URL', help='APIサーバーURL')
@click.pass_context
def cli(ctx, api_url: str):
    """Kugutsushi Search CLI"""
    ctx.ensure_object(dict)
    ctx.obj['api_url'] = api_url


@cli.command()
@click.argument('query')
@click.option('--top-k', '-k', default=5, help='結果数')
@click.option('--mode', '-m', default='hybrid+rerank',
              type=click.Choice(['hybrid', 'hybrid+rerank']),
              help='検索モード')
@click.pass_context
def search(ctx, query: str, top_k: int, mode: str):
    """検索を実行"""
    try:
        resp = requests.get(
            f"{ctx.obj['api_url']}/search",
            params={"query": query, "top_k": top_k, "mode": mode}
        )
        resp.raise_for_status()
        print_results(resp.json()["results"])
    except requests.RequestException as e:
        click.echo(f"エラー: {e}", err=True)


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, help='サブディレクトリも処理')
@click.pass_context
def upload(ctx, path: str, recursive: bool):
    """PDFをアップロード"""
    path = Path(path)
    if path.is_file():
        files = [path] if path.suffix.lower() == '.pdf' else []
    else:
        pattern = '**/*.pdf' if recursive else '*.pdf'
        files = sorted(path.glob(pattern))

    if not files:
        click.echo("PDFファイルが見つかりません", err=True)
        return

    click.echo(f"{len(files)}個のPDFを処理します...")

    for i, f in enumerate(files, 1):
        try:
            with open(f, 'rb') as fp:
                resp = requests.post(
                    f"{ctx.obj['api_url']}/upload",
                    files={'file': (f.name, fp, 'application/pdf')}
                )

            if resp.status_code == 400 and "処理済み" in resp.text:
                click.echo(f"[{i}/{len(files)}] スキップ: {f.name}")
            else:
                resp.raise_for_status()
                result = resp.json()
                click.echo(f"[{i}/{len(files)}] 完了: {f.name} ({result['texts_count']}ページ)")

        except requests.RequestException as e:
            click.echo(f"[{i}/{len(files)}] エラー: {f.name} - {e}", err=True)


@cli.command()
@click.pass_context
def status(ctx):
    """システム状態を表示"""
    try:
        resp = requests.get(f"{ctx.obj['api_url']}/status")
        resp.raise_for_status()
        data = resp.json()

        click.echo(f"整合性: {'OK' if data['integrity'] else 'NG'}")
        click.echo(f"詳細: {data['message']}")
        click.echo(f"ベクトル: {data['vectors']}件")
        click.echo(f"メタデータ: {data['metadata']}件")
        click.echo(f"BM25: {data['bm25']}件")
        click.echo(f"処理済みファイル: {data['processed_files']}件")

    except requests.RequestException as e:
        click.echo(f"エラー: {e}", err=True)


if __name__ == '__main__':
    cli(obj={})
