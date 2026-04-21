"""
AUTH0 SETUP AND VALIDATION GUIDE
Complete guide for configuring and testing Auth0 integration

This guide will walk through:
1. Auth0 dashboard configuration
2. Environment variable setup
3. End-to-end testing validation
4. Role-based access control verification
"""

# =============================================================================
# STEP 1: AUTH0 DASHBOARD CONFIGURATION
# =============================================================================

## 1.1 Create Auth0 Account and Application
1. Go to https://auth0.com/ and create account (free tier available)
2. Navigate to Applications → Create Application
3. Choose "Regular Web Applications" (NOT Single Page Application)
4. Name your application (e.g., "Capsico Inference App")

## 1.2 Configure Application Settings
In your Auth0 application settings, configure these URLs:

**Allowed Callback URLs:**
```
http://127.0.0.1:8080/auth/callback
http://localhost:8080/auth/callback
```

**Allowed Logout URLs:**
```
http://127.0.0.1:8080/
http://localhost:8080/
```

**Allowed Web Origins:**
```
http://127.0.0.1:8080
http://localhost:8080
```

## 1.3 Get Your Credentials
From the Auth0 application "Settings" tab, copy:
- Domain (looks like: your-tenant.auth0.com)
- Client ID (long alphanumeric string)
- Client Secret (long alphanumeric string - keep secure!)

# =============================================================================
# STEP 2: ENVIRONMENT VARIABLE CONFIGURATION
# =============================================================================

## 2.1 Update .env File
Replace placeholder values in your .env file with real Auth0 credentials:

```env
# Database Configuration (REQUIRED)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=mobilab_app
DB_USER=mobilab_user
DB_PASS=mobilab_pass

# Auth0 Configuration (REQUIRED for authentication)
AUTH0_DOMAIN=your-actual-tenant.auth0.com
AUTH0_CLIENT_ID=your_actual_client_id_here
AUTH0_CLIENT_SECRET=your_actual_client_secret_here
AUTH0_CALLBACK_URL=http://127.0.0.1:8080/auth/callback
```

## 2.2 Verify Configuration
After updating .env, restart your Flask app and check that:
- No "Auth0 not configured" warnings in startup logs
- Config shows AUTH0_ENABLED=True in runtime test

# =============================================================================
# STEP 3: USER AND ROLE SETUP
# =============================================================================

## 3.1 Create Test Users
In Auth0 Dashboard → User Management → Users:

1. **Create Regular User:**
   - Email: test-user@example.com
   - Password: (set a secure test password)

2. **Create Admin User:**
   - Email: test-admin@example.com
   - Password: (set a secure test password)

## 3.2 Configure User Roles
Auth0 requires custom setup for roles. Choose ONE method:

### Method A: App Metadata (Simpler)
1. Go to Users → Select user → Details tab
2. Scroll to "app_metadata" section
3. Add this JSON:
   ```json
   {
     "role": "user"
   }
   ```
   For admin user, use `"role": "admin"`

### Method B: Custom Claims via Rules (More Advanced)
1. Go to Auth Pipeline → Rules → Create Rule
2. Choose "Empty rule" template
3. Name: "Add role to tokens"
4. Code:
   ```javascript
   function (user, context, callback) {
     const namespace = 'https://mobilab.app/';
   const assignedRoles = (user.app_metadata || {}).role || 'user';

   context.idToken[namespace + 'role'] = assignedRoles;
   context.accessToken[namespace + 'role'] = assignedRoles;

     callback(null, user, context);
   }
   ```

# =============================================================================
# STEP 4: END-TO-END TESTING CHECKLIST
# =============================================================================

## 4.1 Preparation
- [ ] Auth0 application configured with correct URLs
- [ ] Real credentials added to .env file
- [ ] Test users created with roles assigned
- [ ] Flask app restarted after .env changes
- [ ] MySQL database running and accessible

## 4.2 Basic Authentication Flow
Test each step in order:

1. **App Startup:**
   - [ ] Flask starts without Auth0 warnings
   - [ ] Visit http://127.0.0.1:8080 - home page loads
   - [ ] Navigation shows "Login" link (not "Auth Disabled")

2. **Login Flow:**
   - [ ] Click "Login" or visit /auth/login
   - [ ] Redirects to Auth0 login page
   - [ ] Auth0 page shows your application name
   - [ ] Login with test-user@example.com succeeds
   - [ ] Redirects back to home page automatically

3. **Authenticated State:**
   - [ ] Navigation shows "Profile" and "Logout" links
   - [ ] No "Login" link visible when authenticated
   - [ ] Visit /profile shows user information
   - [ ] User data displays correctly (email, role, etc.)

4. **Session Persistence:**
   - [ ] Refresh page - still logged in
   - [ ] Close/reopen browser tab - still logged in (until session expires)
   - [ ] Visit /auth/user API endpoint - returns user JSON

5. **Logout Flow:**
   - [ ] Click "Logout" or visit /auth/logout
   - [ ] Redirects to Auth0 logout page
   - [ ] Redirects back to home page
   - [ ] Navigation shows "Login" link again
   - [ ] Visit /profile now redirects to login

## 4.3 Database Integration Testing
After successful login, verify:

1. **User Record Creation:**
   ```sql
   SELECT * FROM users WHERE email = 'test-user@example.com';
   ```
   - [ ] User record exists in database
   - [ ] auth0_sub field populated
   - [ ] email, display_name correct
   - [ ] role-based behavior follows Auth0 claim (DB role is not used for authorization)
   - [ ] last_login_at timestamp recent

2. **User Record Updates:**
   - [ ] Login again with same user
   - [ ] last_login_at updates to new timestamp
   - [ ] No duplicate user records created

## 4.4 Role-Based Access Control
Test with both users:

1. **Regular User (test-user@example.com):**
   - [ ] Can access /profile
   - [ ] Cannot access /admin (should get 403 Forbidden)
   - [ ] Profile shows role as "User"

2. **Admin User (test-admin@example.com):**
   - [ ] Can access /profile
   - [ ] Can access /admin (should see admin panel)
   - [ ] Profile shows role as "Admin"

## 4.5 Error Handling and Edge Cases

1. **Database Connectivity:**
   - [ ] Stop MySQL temporarily
   - [ ] Try to login → should get 503 Service Unavailable
   - [ ] Start MySQL → login works normally

2. **Session Expiration:**
   - [ ] Wait for session timeout (default 1 hour, or modify for testing)
   - [ ] Visit /profile → should redirect to login
   - [ ] Login again → works normally

3. **Invalid Tokens:**
   - [ ] Manually corrupt session data
   - [ ] App handles gracefully without crashes

# =============================================================================
# STEP 5: ADMIN PANEL - AUTH0 MANAGEMENT API SETUP
# =============================================================================

The admin panel (User Management) requires a SEPARATE Machine-to-Machine (M2M)
application in Auth0 to call the Management API. Your regular web app credentials
CANNOT be used for this - you'll get a 403 error.

## 5.1 Create M2M Application in Auth0

1. Go to Auth0 Dashboard → Applications → Applications
2. Click "Create Application"
3. Name: "Capsico Management API" (or similar)
4. Select "Machine to Machine Applications"
5. Click "Create"

## 5.2 Authorize for Management API

After creating the M2M app, you'll be prompted to select an API:

1. Select "Auth0 Management API" (shows your tenant domain)
2. Enable these permissions (scopes):
   - `read:users` - List and view users
   - `create:users` - Create new users
   - `update:users` - Update user information
   - `delete:users` - Delete users
   - `read:roles` - List available roles
   - `create:role_members` - Assign roles to users
   - `delete:role_members` - Remove roles from users
3. Click "Authorize"

## 5.3 Create Roles in Auth0

The application expects two roles to exist in Auth0:

1. Go to Auth0 Dashboard → User Management → Roles
2. Create role: **admin**
   - Name: admin
   - Description: Administrator with full access
3. Create role: **user**
   - Name: user
   - Description: Regular user

## 5.4 Find Your Database Connection Name

1. Go to Auth0 Dashboard → Authentication → Database
2. Note the connection name (default is usually "Username-Password-Authentication")
3. This is used when creating users via the admin panel

## 5.5 Update .env File

Add these to your .env file (NOT the web app credentials):

```env
# Auth0 Management API - M2M Application (SEPARATE from your web app)
AUTH0_MANAGEMENT_CLIENT_ID=your_m2m_client_id_here
AUTH0_MANAGEMENT_CLIENT_SECRET=your_m2m_client_secret_here

# Database connection name from Auth0
AUTH0_DB_CONNECTION=Username-Password-Authentication
```

## 5.6 Test Admin Panel

After configuration:

1. Restart Flask app
2. Login as admin user
3. Go to /admin/users
4. Should see user list (no 403 error)
5. Try adding a user - should succeed

## Troubleshooting Management API Issues

**Error: "Auth0 Management API authorization failed (403)"**
- You're using the web app credentials instead of M2M credentials
- Create a separate M2M application as described above
- Copy the M2M Client ID and Secret to AUTH0_MANAGEMENT_CLIENT_ID/SECRET

**Error: "Missing required Auth0 roles in tenant"**
- Create "admin" and "user" roles in Auth0 Dashboard → Roles

**Error: "AUTH0_DB_CONNECTION is required to create users"**
- Set AUTH0_DB_CONNECTION in your .env file
- Find the connection name in Auth0 → Authentication → Database

# =============================================================================
# STEP 6: TECHNICAL VALIDATION
# =============================================================================

## 6.1 JWKS Caching Test
1. Enable DEBUG logging in Flask
2. Login first time → should see JWKS fetch in logs
3. Login second time → should NOT see JWKS fetch (using cache)
4. Wait 6+ minutes → login again → should see new JWKS fetch

## 6.2 Race Condition Test
1. Open 2 browser tabs
2. Login with same user simultaneously
3. Check database → only 1 user record exists
4. No database errors in logs

## 6.3 Concurrent Access Test
1. Login with different users in different browsers
2. All should work without interference
3. Check that user isolation works correctly

# =============================================================================
# STEP 7: TROUBLESHOOTING COMMON ISSUES
# =============================================================================

## Issue: "Auth0 authorization failed"
- Check callback URL exactly matches Auth0 configuration
- Verify domain doesn't have extra characters/spaces

## Issue: "Failed to exchange code for tokens"
- Check Client Secret is correct
- Verify application type is "Regular Web App"

## Issue: "User role not found in Auth0 claims"
- Verify user has role set in app_metadata OR custom rules configured
- Check rule is enabled and runs successfully
- Confirm custom claim key is exactly https://mobilab.app/role

## Issue: Database connection errors during auth
- Verify MySQL is running and accessible
- Check database credentials in .env

## Issue: Session doesn't persist
- Check Flask SECRET_KEY is set
- Verify session configuration in config.py

# =============================================================================
# FINAL VALIDATION CHECKLIST
# =============================================================================

Authentication foundation is COMPLETE when ALL of these pass:

**Mode 1 (Auth0 Disabled):**
- [✓] Already validated in previous testing

**Mode 2 (Auth0 Enabled):**
- [ ] Login redirect works
- [ ] Auth0 callback processes successfully
- [ ] User syncs to database correctly
- [ ] Role extraction and assignment works
- [ ] Protected routes enforce authentication
- [ ] Admin routes enforce role-based access
- [ ] Logout clears session and redirects
- [ ] Session expiration handled gracefully
- [ ] Database errors return 503 (not crashes)
- [ ] JWKS caching prevents excessive Auth0 calls
- [ ] Concurrent logins don't create race conditions
- [ ] All security validations pass

**Only when EVERY item above passes should we proceed to prediction history implementation.**