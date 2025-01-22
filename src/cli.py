import click
import requests
import os
from typing import Optional, List
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def print_search_results(results: List[dict]) -> None:
    """検索結果を表示"""
    for result in results:
        print("-" * 80)
        print(f"スコア: {result['score']:.3f}")
        print(f"テキスト: {result['text']}")
        print()

@click.group()
def cli():
    """Kugutsushi Search CLI - PDFドキュメント検索ツール"""
    pass

@cli.command()
@click.argument('query')
@click.option('--top-k', default=3, help='表示する検索結果の数')
def search(query: str, top_k: int):
    """
    テキストクエリで検索を実行します。
    """
    try:
        response = requests.get(f"{API_BASE_URL}/search", params={
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
def upload(path: str, recursive: bool):
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
            
        total_files = len(list(files))
        if total_files == 0:
            click.echo("PDFファイルが見つかりません。", err=True)
            return
            
        click.echo(f"{total_files}個のPDFファイルを処理します...")
        
        processed = 0
        skipped = 0
        for pdf_file in files:
            try:
                with open(pdf_file, 'rb') as f:
                    files = {'file': (pdf_file.name, f, 'application/pdf')}
                    response = requests.post(f"{API_BASE_URL}/upload", files=files)
                    response.raise_for_status()
                    
                result = response.json()
                if result.get("skipped", False):
                    skipped += 1
                    click.echo(f"スキップ: {pdf_file.name} (既に処理済み)")
                else:
                    processed += 1
                    click.echo(f"処理完了: {pdf_file.name} ({result['texts_count']}件のテキストを追加)")
                    
            except Exception as e:
                click.echo(f"エラー: {pdf_file.name} ({str(e)})", err=True)
                
        click.echo(f"\n処理完了: {processed}個のファイルを処理、{skipped}個のファイルをスキップしました。")
        
    except requests.exceptions.RequestException as e:
        click.echo(f"APIリクエストエラー: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"エラーが発生しました: {str(e)}", err=True)

@cli.command()
def reindex():
    """インデックスを再構築"""
    try:
        response = requests.post(f"{API_BASE_URL}/reindex")
        response.raise_for_status()
        print(response.json()["message"])
    except requests.exceptions.RequestException as e:
        print(f"エラー: {e}")
        if hasattr(e.response, 'json'):
            print(e.response.json()["detail"])

if __name__ == '__main__':
    cli() 