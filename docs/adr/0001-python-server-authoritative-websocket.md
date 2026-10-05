# Python backend ที่เป็นเจ้าของ state เกมทั้งหมด ผ่าน WebSocket

Backend เป็น Python (FastAPI + WebSocket) และเป็นเจ้าของ state ของเกมทั้งหมด (Secret Word, timer, ลำดับ Buzz, คะแนน) โดยเก็บไว้ใน memory ของ process เดียว ส่วน frontend เป็น React + Vite SPA ที่ทำหน้าที่แสดงผลอย่างเดียว เลือก Python เพราะเครื่องมือตัดพยางค์ที่น่าเชื่อถือที่สุดสำหรับภาษาไทย (PyThaiNLP) และภาษาอังกฤษ (CMUdict) อยู่ใน Python และการตรวจ Clue ต้องรันที่ server เลือกให้ server เป็นเจ้าของ state เพราะ Secret Word ห้ามไปถึง client ของ Guesser ไม่ว่ากรณีใด

## Considered Options

- **Node + Socket.IO ทั้ง stack เป็น TypeScript** — ตกไปเพราะตัวตัดพยางค์ไทยใน JS มีน้อยและแม่นน้อยกว่า
- **Firebase/Supabase realtime** — ตกไปเพราะซ่อน Secret Word จาก Guesser ได้ยาก และไม่มีที่ให้ตัวจับเวลาของ server เป็นผู้ตัดสิน

## Consequences

- State อยู่ใน memory: ถ้า restart server ทุก Lobby ที่เปิดอยู่จะหายหมด และยังขยายเป็นหลาย instance ไม่ได้จนกว่าจะย้าย state ไปไว้ที่อื่นที่ทุก instance เข้าถึงร่วมกันได้ (เช่น Redis)
- การถอดเสียงเกิดที่ browser (Web Speech API) จึงใช้ไมค์ได้ดีที่สุดบนเบราว์เซอร์ตระกูล Chromium ส่วนการพิมพ์ใช้ได้ทุกที่
