import click
import requests
import os
from typing import Optional, List
from pathlib import Path

API_BASE_URL = os.environ.get("KUGUTSUSHI_API_URL", "http://localhost:8000")

def print_search_results(results: List[dict]) -> None:
    """検索結果を表示"""
    for result in results:
        print("-" * 80)
        print(f"書籍: {Path(result['file']).name}")
        print(f"ページ: {result['page'] + 1}")  # 0-indexedを1-indexedに変換
        print(f"スコア: {result['score']:.3f}")
        print(f"テキスト: {result['text']}")
        print()

def upload_pdf_files(files: List[Path], api_url: str) -> None:
    """PDFファイルをアップロードして処理します。"""
    if not files:
        click.echo("PDFファイルが見つかりません。", err=True)
        return
        
    click.echo(f"{len(files)}個のPDFファイルを処理します...")
    
    processed = 0
    skipped = 0
    for pdf_file in files:
        try:
            with open(pdf_file, 'rb') as f:
                files = {'file': (pdf_file.name, f, 'application/pdf')}
                response = requests.post(f"{api_url}/upload", files=files)
                response.raise_for_status()
                
            result = response.json()
            if result.get("skipped", False):
                skipped += 1
                click.echo(f"スキップ: {pdf_file.name} (既に処理済み)")
            else:
                processed += 1
                click.echo(f"処理完了: {pdf_file.name} ({result['texts_count']}件のテキストを追加)")
                
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e.response, 'json'):
                error_json = e.response.json()
                error_detail = f"\nエラー詳細: {error_json.get('detail', '')}"
                if 'traceback' in error_json:
                    error_detail += f"\n\nスタックトレース:\n{error_json['traceback']}"
            click.echo(f"エラー: {pdf_file.name} ({str(e)}){error_detail}", err=True)
        except Exception as e:
            click.echo(f"エラー: {pdf_file.name} ({str(e)})", err=True)
            
    click.echo(f"\n処理完了: {processed}個のファイルを処理、{skipped}個のファイルをスキップしました。")

@click.group()
@click.option('--api-url', default=API_BASE_URL, help='APIサーバーのURL')
@click.pass_context
def cli(ctx, api_url: str):
    """Kugutsushi Search CLI - PDFドキュメント検索ツール"""
    ctx.ensure_object(dict)
    ctx.obj['api_url'] = api_url

@cli.command()
@click.argument('query')
@click.option('--top-k', default=3, help='表示する検索結果の数')
@click.pass_context
def search(ctx, query: str, top_k: int):
    """
    テキストクエリで検索を実行します。
    """
    try:
        response = requests.get(f"{ctx.obj['api_url']}/search", params={
            "query": query,
            "top_k": top_k
        })
        response.raise_for_status()
        
        results = response.json()["results"]
        
        print_search_results(results)
        
    except requests.exceptions.RequestException as e:
        click.echo(f"APIリクエストエラー: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"エラーが発生しました: {str(e)}", err=True)

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive/--no-recursive', '-r', default=False, help='サブディレクトリも含めて処理するかどうか')
@click.pass_context
def upload(ctx, path: str, recursive: bool):
    """
    PDFファイルまたはディレクトリをアップロードしてインデックスに追加します。
    PATHにディレクトリを指定した場合、その中のPDFファイルを全て処理します。
    """
    try:
        path = Path(path)
        if path.is_file():
            if not path.suffix.lower() == '.pdf':
                click.echo(f"スキップ: {path} (PDFファイルではありません)", err=True)
                return
            files = [path]
        else:
            pattern = '**/*.pdf' if recursive else '*.pdf'
            files = sorted(path.glob(pattern))
        
        upload_pdf_files(files, ctx.obj['api_url'])
        
    except requests.exceptions.RequestException as e:
        click.echo(f"APIリクエストエラー: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"エラーが発生しました: {str(e)}", err=True)

@cli.command()
@click.pass_context
def reindex(ctx):
    """インデックスを再構築"""
    try:
        response = requests.post(f"{ctx.obj['api_url']}/reindex")
        response.raise_for_status()
        click.echo("インデックスの再構築が完了しました")
    except requests.exceptions.RequestException as e:
        print(f"エラー: {e}")
        if hasattr(e.response, 'json'):
            print(e.response.json()["detail"])

if __name__ == '__main__':
    cli(obj={}) 