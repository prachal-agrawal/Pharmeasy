# Image upload flow: frontend → backend → storage

This document describes how the Medkart / MathuraPharmeasy stack sends **multiple images** from the UI, how the API **accepts** them, and how files end up **on disk** and in the **database**.

There are two main flows:

1. **Checkout — prescription images** (customer): one HTTP upload per file, then URLs are sent with the order JSON.
2. **Admin — medicine gallery images**: many files in a **single** multipart request under the same field name `images`.

---

## Shared concepts

### Where files live on disk

- **Directory:** `UPLOAD_DIR` from settings (default `./public/uploads`, configurable via `.env`).
- **Public URL path:** responses use paths like `/uploads/<filename>` (not full `http://...` URLs).
- **Serving files:** FastAPI mounts static files so `/uploads` is served from `./public/uploads` (`main.py`). The Vite dev server proxies `/uploads` to the backend (`frontend/vite.config.js`), so the browser can load images during local development.

### Multipart form data

Browsers send file uploads as `multipart/form-data`. The frontend sets `Content-Type: multipart/form-data` and lets the browser set the boundary (do not set the boundary manually).

---

## Flow A: Multiple prescription images at checkout

### What the UI does

- **Component:** `frontend/src/pages/Checkout.jsx`
- User can select **several** prescription files. State keeps:
  - `rxFiles` — `File[]`
  - `rxPreviews` — object URLs for thumbnails
  - `rxUrls` — server-returned paths (`/uploads/...`) or `null` until uploaded

**Upload strategy:** each file is uploaded with a **separate** POST (parallelized with `Promise.all`), not one request with multiple parts.

- **API helper:** `ordersAPI.uploadPrescription(file)` in `frontend/src/utils/api.js`
  - Builds `FormData`, appends **one** field: `file`
  - POST ` /api/orders/upload-prescription` with `multipart/form-data`

**When placing the order**, if any cart item `requires_rx`, the UI ensures all files are uploaded, then collects the list of `/uploads/...` strings and includes them in the order payload as `prescription_urls` (JSON array of strings).

### What the backend does

- **Route:** `POST /api/orders/upload-prescription` in `backend/routes/orders_router.py`
  - Expects **`file`** (single `UploadFile`).
  - Validates `Content-Type` is one of: `image/jpeg`, `image/png`, `image/webp`, `image/gif`.
  - Writes to `UPLOAD_DIR` with a name like `rx_<userId>_<timestamp>.<ext>`.
  - Returns `{"url": "/uploads/<filename>"}`.

- **Order creation:** `POST /api/orders` with body model `OrderIn`, field `prescription_urls: Optional[List[str]]`.
  - For each URL in `prescription_urls`, inserts a row into **`order_prescriptions`** (`order_id`, `url`).
  - The actual bytes are **already** on disk from the upload step; the order only stores the path.

### Why not one multipart order with all Rx files?

The current design uses **upload-then-order**: each prescription is stored first; the order references stable paths. That keeps order placement as JSON and avoids large multipart order endpoints.

---

## Flow B: Admin — multiple medicine images in one request

### What the UI does

- **Component:** `frontend/src/pages/admin/AdminMedicines.jsx`
- On save, the app builds **one** `FormData` with text fields (`name`, `brand`, `variants` JSON, etc.) and **appends each new image file** with the **same** field name:

  ```javascript
  form.pendingFiles.forEach(f => fd.append('images', f))
  ```

- **Edit mode:** sends `existing_image_urls` as a JSON string of paths to **keep**; new files are appended as additional `images` parts. The backend merges kept URLs + newly saved paths.

- **API:** `adminAPI.addMedicine(formData)` and `adminAPI.updateMedicine(id, formData)` in `frontend/src/utils/api.js` — both use `POST` / `PUT` with `multipart/form-data`.

### What the backend does

- **Routes:** `POST /api/admin/medicines` and `PUT /api/admin/medicines/{med_id}` in `backend/routes/admin_router.py`.

- **Important implementation detail:** FastAPI’s `File()` binding often only receives **one** file when multiple parts share the name `images`. To reliably get **every** file, the handlers call `await request.form()` and use **`form.getlist("images")`** to collect all parts named `images` (see `_images_from_multipart` and `_collect_uploads_multipart`).

- **Saving each file:** `_save_image` writes under `UPLOAD_DIR` with names like `med_<random>.<ext>` and returns `/uploads/...`.

- **Database:**
  - **`medicines.image_urls`** — JSON array of strings (full gallery).
  - **`medicines.image_url`** — first image for backward compatibility / primary thumbnail.

On **update**, if `existing_image_urls` and/or new `images` are present, the gallery columns are replaced with `kept + new_uploads`; otherwise image fields are left unchanged.

### Authentication

Admin routes use `require_admin` (JWT). Order prescription upload uses `get_current_user` (logged-in customer).

---

## Quick reference

| Concern | Prescription (checkout) | Medicine (admin) |
|--------|---------------------------|------------------|
| Frontend | `FormData` with key **`file`**, one request per file | `FormData` with repeated **`images`** keys in one request |
| Endpoint | `POST /api/orders/upload-prescription` | `POST` or `PUT /api/admin/medicines` |
| Disk filename prefix | `rx_...` | `med_...` |
| DB storage | `order_prescriptions.url` (per image row) | `medicines.image_urls` (JSON) + `image_url` (first) |

---

## Related files

| Layer | Files |
|-------|--------|
| Checkout UI | `frontend/src/pages/Checkout.jsx` |
| Admin UI | `frontend/src/pages/admin/AdminMedicines.jsx` |
| API client | `frontend/src/utils/api.js` |
| Orders API | `backend/routes/orders_router.py` |
| Admin API | `backend/routes/admin_router.py` |
| Static mounts | `backend/main.py` |
| Upload directory | `backend/config.py` (`UPLOAD_DIR`) |
| Dev proxy | `frontend/vite.config.js` |
