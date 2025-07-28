I assume you have npm installed already

Also update th

For running the frontend do the following, 
1. rm -rf node_modules package-lock.json
2. npm i
3. npm run dev 

Now it should be running on your localhost

For Backend Server run the following commands
1. python3 -m venv venv
2. source venv/bin/activate
3. pip install -r requirements.txt
4. python manage.py createsuperuser
5. python manage.py migrate         
6. python manage.py runserver 8000  

For viewing the DB go the port specified in the terminal when you do runserver and do /admin after
For me this is http://127.0.0.1:8000/admin
and then specify the credentials when you made a super user

Client will run on localhost:5173 (Your React Port) and will connect to
WebSocket on ws://localhost:8000/ws/chat/ for making calls to the server

I Used the following,
React + TypeScript for application Design
Django/Python for Backend/Server Logic
Default SQLite DataBase from Django for storing client session data

