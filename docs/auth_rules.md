# Authentication Rules (Non-Negotiable)

1. Authentication is handled by Amazon Cognito
2. Backend ONLY verifies JWT tokens
3. Backend controls all authorization logic
4. NO passwords stored in local database
5. User identity is Cognito `sub` claim
6. All queries MUST be tenant-scoped