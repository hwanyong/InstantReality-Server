import asyncio
from aiohttp import web

@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })
    try:
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except web.HTTPException as e:
        # Allow 404/405 to propagate naturally (or just return them)
        return e
    except Exception as e:
        return web.Response(status=500, text=f"{type(e).__name__}: {e}")

async def offer(request):
    return web.Response(text="ok")

async def test():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post("/offer", offer)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 9000)
    await site.start()
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # Test 1: POST /offer (Should be 200)
        async with session.post('http://localhost:9000/offer') as resp:
            print(f"POST /offer: {resp.status}")
            
        # Test 2: OPTIONS /offer (Should be 200 if middleware works, or 405/404 if not)
        async with session.options('http://localhost:9000/offer') as resp:
            print(f"OPTIONS /offer: {resp.status}")
            
        # Test 3: POST /offer/ (Trailing slash)
        async with session.post('http://localhost:9000/offer/') as resp:
            print(f"POST /offer/: {resp.status}")

        # Test 4: POST //offer (Double slash)
        async with session.post('http://localhost:9000//offer') as resp:
            print(f"POST //offer: {resp.status}")

    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(test())
