from fastapi import FastAPI

# Create a minimal FastAPI app
app = FastAPI(title="WhatthecV API (Minimal)")

@app.get("/")
def read_root():
    return {"message": "Minimal API is running on Vercel"}

@app.get("/api/v1/test")
def test_endpoint():
    return {"status": "success", "message": "Minimal API is working"} 