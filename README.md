#  Cloud Service Access Management System

A backend FastAPI project to manage access to cloud services based on user subscriptions and permissions.

## Authors

**Indrayani Bhosale**  
**CWID:** 842614851  

**Janya Jaiswal**  
**CWID:** 878062934  

**Shrutik Kupekar**  
**CWID:** 884426727  

##  Features

- Role-based access (Admin/Customer)
- Subscription plans with API limits
- Usage tracking and access control
- Mock token-based login for simplicity
- Swagger UI for testing endpoints

##  Technologies Used

- Python 3.10+
- FastAPI
- Swagger UI
- MongoDB 

##  How to Run

```bash
git clone https://github.com/shrutikkupekar/WebBackend-Final-Project.git
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
uvicorn main:app --reload






