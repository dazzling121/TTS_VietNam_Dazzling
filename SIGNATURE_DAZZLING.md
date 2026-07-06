# Chu Ky Du An Dazzling

Du an nay duoc gan chu ky ma hoa `Dazzling` bang file khoa trung tam `services/dazzling_lock.py` va file manifest `PROJECT_SIGNATURE.json`.

Co che hoat dong:

- `services/dazzling_lock.py` la o khoa cong khai cua du an. File nay chua public key Ed25519 cua Dazzling.
- Private key nam trong `private/dazzling_private_key.pem` va bi `.gitignore` loai khoi GitHub.
- Moi file quan trong trong du an duoc tinh `sha256` va ghi vao `PROJECT_SIGNATURE.json`.
- `PROJECT_SIGNATURE.json` duoc ky bang private key cua Dazzling.
- Ung dung kiem tra chu ky so bang public key trong `services/dazzling_lock.py` khi khoi dong, sau buoc tu dong cap nhat GitHub.
- Neu file da ky bi sua, thieu, them file code moi chua ky, file khoa bi doi, hoac manifest bi thay doi, ung dung se dung va thong bao loi.
- Trang `Cai dat` co nut kiem tra chu ky `Dazzling` de xem trang thai ngay trong giao dien.

Sau khi chu du an chu dong sua code, hay ky lai:

```bash
python scripts/sign_project.py
```

Trong moi truong phat trien noi bo dang tin cay, co the tam bo qua kiem tra:

```bash
TTS_STUDIO_ALLOW_UNSIGNED=1 python app.py
```

Luu y quan trong:

- Neu mot nguoi da co toan bo source code va quyen sua file, khong co cach nao khoa tuyet doi de ho khong xoa doan kiem tra.
- Co che public/private key nay giup phat hien sua doi trai phep, tao bang chung ve tinh nguyen ban, va lam viec an cap/doi ten du an kho hon vi nguoi khac khong co private key Dazzling de ky lai manifest hop le.
- De bao ve manh hon khi phat hanh thuong mai, nen dong goi ung dung thanh ban binary, dung license ro rang, va giu khoa ky that o moi truong rieng.
