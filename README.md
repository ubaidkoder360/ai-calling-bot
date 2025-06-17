✅ Run it
uvicorn main:app --reload

✅ Call It
You can use Postman or a frontend form to POST a CSV to:

POST /call-from-csv/

Body: multipart/form-data with field file.

☎ Example CSV format

Just numbers, no header:

+923001234567
+923451234567
+923211234567
