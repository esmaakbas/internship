"""
STEP-BY-STEP AUTH0 ACTION CONFIGURATION
Complete guide to add role claims to ID tokens

IMPORTANT: This must be done in the Auth0 Dashboard, not in code.
"""

# =============================================================================
# STEP 1: ACCESS AUTH0 ACTIONS
# =============================================================================

1. Open your browser and go to: https://manage.auth0.com/
2. Log in to your Auth0 account
3. Make sure you're in the correct tenant (dev-db75eauyteg5isyb.us.auth0.com)

# =============================================================================
# STEP 2: NAVIGATE TO ACTIONS
# =============================================================================

4. In the left sidebar, click: "Actions"
5. Click: "Flows"
6. You should see a list of flows including "Login"

# =============================================================================
# STEP 3: OPEN LOGIN FLOW
# =============================================================================

7. Click on: "Login" flow
8. You'll see a visual flow with "Start" and "Complete" nodes connected by a line
9. There may be existing actions in the flow or just the basic flow

# =============================================================================
# STEP 4: CREATE CUSTOM ACTION
# =============================================================================

10. On the right side panel, click: "Add Action"
11. Click: "Build Custom"
12. Fill in the form:
    - Name: "Add Role to Token"
    - Trigger: "Login / Post Login" (should be pre-selected)
    - Runtime: "Node.js 18" (recommended)
13. Click: "Create"

# =============================================================================
# STEP 5: ADD THE CODE
# =============================================================================

14. You'll see a code editor. REPLACE ALL the default code with this:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  // Namespace for custom claims (must start with https://)
  const namespace = 'https://mobilab.app/';

   // Read Auth0-assigned roles and normalize to a single app role.
   // If multiple roles are assigned, admin wins over user.
   const assignedRoles = event.authorization?.roles || [];
   const role = assignedRoles.includes('admin') ? 'admin' : 'user';

  // Add role to ID token as a custom claim
  api.idToken.setCustomClaim(`${namespace}role`, role);

  // Optional: Log for debugging (can be removed later)
  console.log(`Added role '${role}' to ID token for user: ${event.user.email}`);
};
```

15. Click: "Deploy" (button in top right)
16. Wait for "Action deployed successfully" message

# =============================================================================
# STEP 6: ADD ACTION TO LOGIN FLOW
# =============================================================================

17. Click: "Back to flow" or navigate back to Actions → Flows → Login
18. You should see your new "Add Role to Token" action in the right panel
19. DRAG the "Add Role to Token" action from the right panel into the flow
20. Place it between "Start" and "Complete" (it will snap into place)
21. The flow should now look like: Start → Add Role to Token → Complete

# =============================================================================
# STEP 7: APPLY THE CHANGES
# =============================================================================

22. Click: "Apply" (button in top right)
23. You should see a success message: "Flow updated successfully"

# =============================================================================
# STEP 8: VERIFICATION
# =============================================================================

24. The Login flow should now show:
    - Start (circle)
    - → Add Role to Token (rectangle with your action name)
    - → Complete (circle)

25. The action should show as "Active" or "Deployed"

# =============================================================================
# STEP 9: TEST THE LOGIN
# =============================================================================

26. Go back to your Flask app: http://127.0.0.1:8080
27. Click "Login"
28. Complete the Auth0 login process
29. You should now successfully log in and see your profile

# =============================================================================
# TROUBLESHOOTING
# =============================================================================

If it still doesn't work:

A) Check Action Logs:
   - Actions → Flows → Login → Click your action → "Logs" tab
   - Look for any error messages

B) Verify User Metadata:
   - User Management → Users → Click your test user
   - Verify user has Auth0 role assignment: admin or user

C) Check Flask Logs:
   - Look for: "Role claim found: admin" in your terminal
   - Should NOT see: "Role claim not found"

D) Common Issues:
   - Action not deployed: Make sure you clicked "Deploy"
   - Action not in flow: Make sure you dragged it into the flow
   - Flow not applied: Make sure you clicked "Apply"
   - Wrong namespace: Must match exactly 'https://mobilab.app/role'

# =============================================================================
# EXPECTED RESULT
# =============================================================================

After successful configuration:
✓ Login works without errors
✓ User appears in Flask 'users' table (role in DB is not used for authorization)
✓ Profile page shows user information
✓ Admin users can access /admin route
✓ Regular users get 403 on /admin route

# =============================================================================
# FINAL CLAIM CONTRACT
# =============================================================================

Your Auth0 Action and Flask backend must use this exact claim key:

- Claim key: https://mobilab.app/role
- Value: "admin" or "user"

Do not use https://mobilab.app/roles for backend role checks in this app.