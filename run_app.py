import uvicorn


def main() -> None:
    """Run the FastAPI application with uvicorn."""
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
