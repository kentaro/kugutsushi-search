import uvicorn
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """
    Kugutsushi Search APIサーバーを起動します。
    """
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )

if __name__ == "__main__":
    main() 