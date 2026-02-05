# import asyncio
# import json
# import websockets

# async def main():
#     async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
#         print(await ws.recv())  # session.ready
#         await ws.send(json.dumps({"type": "session.start"}))
#         print(await ws.recv())  # status

# asyncio.run(main())

# [2] ================================
# import asyncio
# import json
# import websockets

# async def main():
#     async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
#         print("1)", await ws.recv())  # session.ready

#         await ws.send(json.dumps({
#             "type": "session.start",
#             "payload": {
#                 "first_question": "지원 직무의 특징과 역할에 대해 아는 대로 말해주세요! (700자)",
#                 "use_llm": False
#             }
#         }))

#         print("2)", await ws.recv())  # question or debug
#         print("3)", await ws.recv())  # question or debug

#         await ws.send(json.dumps({
#             "type": "answer",
#             "payload": {"text": "데이터를 수집·정리하고 문제를 구조화해 의사결정을 돕는 역할이라고 생각합니다."}
#         }))

#         print("4)", await ws.recv())
#         print("5)", await ws.recv())

# asyncio.run(main())


# [3]
import asyncio
import json
import requests
import websockets

API = "http://127.0.0.1:8000"

async def main():
    # 1) REST로 세션 시작
    r = requests.post(f"{API}/session/start", json={
        "first_question": "지원 직무의 특징과 역할에 대해 아는 대로 말해주세요! (700자)",
        "use_llm": False
    })
    r.raise_for_status()
    data = r.json()
    session_id = data["session_id"]
    print("REST start:", data)

    # 2) WS로 해당 세션에 붙기
    async with websockets.connect(f"ws://127.0.0.1:8000/ws?session_id={session_id}") as ws:
        print("1)", await ws.recv())  # session.ready

        # answer
        await ws.send(json.dumps({"type": "answer", "payload": {"text": "데이터를 수집·정리하고 문제를 구조화해 의사결정을 돕는 역할이라 생각합니다."}}))
        print("2)", await ws.recv())  # question or debug
        print("3)", await ws.recv())  # question or debug

asyncio.run(main())

