# Admin User Management - End-to-End Test Plan

**Date:** March 8, 2026  
**Project:** ferrouslabs-auth-system  
**Purpose:** Comprehensive UI testing for Priority 2 - Admin Panels for User Management

---

## 🎯 Pre-Test Setup

### Required Environment
1. **PostgreSQL** running (Docker container via `.\setup-postgres.ps1`)
2. **Backend** running (`cd backend && uvicorn app.main:app --reload --port 8001`)
3. **Frontend** running (`cd frontend && npm run dev`)
4. **Test Users** - At least 3 users with different roles:
   - Platform Admin
   - Tenant Admin/Owner
   - Regular Member

### Test Data Preparation
- [ ] Database has at least 2 tenants
- [ ] Each tenant has multiple users (3-5 recommended)
- [ ] Users have varied roles (owner, admin, member)
- [ ] At least one suspended user exists
- [ ] At least one active invitation exists

---

## 📋 Test Scenarios

### **SCENARIO 1: Platform Admin - Full Access Test**

**Tester Login:** Platform Admin

#### 1.1 List Users
- [ ] Navigate to Admin Dashboard at `/admin`
- [ ] Verify platform admin badge displays in header
- [ ] Verify user list loads successfully
- [ ] Verify all columns display: Email, Name, Role, Status, Actions
- [ ] Verify user count matches expected database count
- [ ] Verify no console errors

#### 1.2 Search & Filter
- [ ] **Search by Email:** Type partial email → verify results filter instantly
- [ ] **Search by Name:** Type partial name → verify results update
- [ ] **Clear Search:** Remove search text → verify all users return
- [ ] **Role Filter:** Select "Admin" → verify only admins display
- [ ] **Role Filter:** Select "Member" → verify only members display
- [ ] **Role Filter:** Select "All Roles" → verify all users return
- [ ] **Status Filter:** Select "Active" → verify only active users show
- [ ] **Status Filter:** Select "Suspended" → verify only suspended users show
- [ ] **Status Filter:** Select "All" → verify all users return
- [ ] **Combined Filters:** Use search + role filter + status filter simultaneously
- [ ] Verify filter combinations work correctly

#### 1.3 Sorting
- [ ] Click "Email" column header → verify sort ascending (A-Z)
- [ ] Click "Email" header again → verify sort descending (Z-A)
- [ ] Click "Name" column → verify sort switches to name field
- [ ] Click "Role" column → verify sort by role
- [ ] Verify sort indicator (arrow) displays correctly

#### 1.4 Pagination
- [ ] Note total user count
- [ ] Change page size to 5 → verify only 5 users display per page
- [ ] Verify pagination controls appear if users > page size
- [ ] Navigate to page 2 → verify different users display
- [ ] Navigate back to page 1 → verify original users return
- [ ] Change page size to 25 → verify pagination adjusts
- [ ] Apply filter → verify pagination resets to page 1

**Expected:** All list, search, filter, sort, and pagination features work smoothly

---

### **SCENARIO 2: Invite New User**

**Tester Login:** Tenant Admin

#### 2.1 Basic Invitation Flow
- [ ] Verify "Invite User" button visible in dashboard header
- [ ] Click "Invite User" button
- [ ] Modal opens successfully with proper title
- [ ] Verify email input field present
- [ ] Verify role selector present (Admin, Member options)
- [ ] Enter valid email: `newuser1@test.com`
- [ ] Select role: "Member"
- [ ] Click "Send Invitation" button
- [ ] Verify loading state on button
- [ ] Verify success toast appears: "Invitation sent successfully"
- [ ] Verify modal closes automatically
- [ ] Verify user list refreshes (refresh key increments)

#### 2.2 Invitation Validation & Error Handling
- [ ] Click "Invite User"
- [ ] Leave email empty → Click submit → Verify validation error
- [ ] Enter invalid email: `notanemail` → Verify validation error
- [ ] Enter malformed email: `user@` → Verify validation error
- [ ] Enter existing user email → Verify error: "User already invited" or similar
- [ ] Try inviting same email twice → Verify duplicate protection
- [ ] Click close/cancel → Verify modal closes without action
- [ ] Verify no duplicate requests sent (check network tab)

#### 2.3 Admin Role Invitation
- [ ] Click "Invite User"
- [ ] Enter email: `newadmin@test.com`
- [ ] Select role: "Admin"
- [ ] Click "Send Invitation"
- [ ] Verify invitation creates successfully
- [ ] Verify invitation shows in pending invitations (if list exists)

#### 2.4 Email Delivery Verification
- [ ] Check backend logs for email send confirmation
- [ ] Verify invitation token generated
- [ ] Verify invitation URL format: `{FRONTEND_URL}/invite/{token}`
- [ ] Copy invitation token from logs or database
- [ ] Verify invitation expiry set correctly

**Expected:** Invitation flow works end-to-end with proper validation

---

### **SCENARIO 3: Change User Roles**

**Tester Login:** Tenant Admin

#### 3.1 Promote Member to Admin
- [ ] Find a user with "Member" role in the list
- [ ] Locate role dropdown/selector for that user
- [ ] Click to open role selector
- [ ] Verify "Admin" and "Member" options visible
- [ ] Select "Admin" from dropdown
- [ ] Verify loading/processing spinner appears
- [ ] Verify success toast: "Updated {email}'s role to Admin"
- [ ] Verify role immediately updates in the UI
- [ ] Click "Refresh" button → Verify role persists
- [ ] Refresh entire page → Verify role still shows "Admin"
- [ ] Check database directly → Verify membership.role = 'admin'

#### 3.2 Demote Admin to Member
- [ ] Find a user with "Admin" role (NOT yourself, NOT last owner)
- [ ] Open role dropdown
- [ ] Select "Member"
- [ ] Verify success toast
- [ ] Verify role updates to "Member" in UI
- [ ] Verify change persists after refresh

#### 3.3 Protected Role Changes - Last Owner Protection
- [ ] Identify the last/only owner in the tenant
- [ ] Try changing owner's role to "Admin" or "Member"
- [ ] Verify error toast: "Cannot remove last owner"
- [ ] Verify role does NOT change
- [ ] Verify user remains as "Owner"
- [ ] Refresh → Verify protection held

#### 3.4 Self-Role Change Test
- [ ] Try changing your own role (current logged-in admin)
- [ ] System should either prevent or warn about this
- [ ] Verify appropriate safeguards exist

**Expected:** Role changes work with proper protection rules enforced

---

### **SCENARIO 4: Suspend & Unsuspend Users**

**Tester Login:** Admin with suspension privileges

#### 4.1 Suspend Active User
- [ ] Find an active user in the list
- [ ] Verify user shows "Active" status badge
- [ ] Click "Suspend" button for that user
- [ ] Verify confirmation dialog appears
- [ ] Verify dialog title: "Suspend User"
- [ ] Verify dialog message includes user email
- [ ] Verify dialog warns about losing access
- [ ] Click "Cancel" → Verify dialog closes, nothing happens
- [ ] Click "Suspend" button again
- [ ] Click "Confirm" in dialog
- [ ] Verify processing state (button disabled/spinner)
- [ ] Verify success toast: "Suspended {email} successfully"
- [ ] Verify user status immediately changes to "Suspended"
- [ ] Verify suspended badge/indicator displays (color/icon)
- [ ] Apply status filter "Suspended" → Verify user appears
- [ ] Apply status filter "Active" → Verify user disappears
- [ ] Refresh page → Verify suspension persists

#### 4.2 Unsuspend User
- [ ] Find a suspended user (use status filter "Suspended")
- [ ] Verify "Suspended" badge displays
- [ ] Click "Unsuspend" button
- [ ] Verify confirmation dialog appears
- [ ] Verify dialog title: "Unsuspend User"
- [ ] Verify dialog message includes user email
- [ ] Click "Confirm"
- [ ] Verify success toast: "Unsuspended {email} successfully"
- [ ] Verify user status changes to "Active"
- [ ] Apply status filter "Active" → Verify user appears
- [ ] Apply status filter "Suspended" → Verify user disappears
- [ ] Refresh page → Verify active status persists

#### 4.3 Suspended User Login Verification
- [ ] Note email of a suspended user
- [ ] Logout from admin account
- [ ] Navigate to login page
- [ ] Try logging in with suspended user credentials
- [ ] Verify login is BLOCKED (Cognito or backend should reject)
- [ ] Verify appropriate error message displays
- [ ] Login back as admin
- [ ] Unsuspend that user
- [ ] Logout and login as the unsuspended user
- [ ] Verify login NOW WORKS
- [ ] Verify user can access permitted pages

**Expected:** Suspend/unsuspend functions work correctly and enforcement is immediate

---

### **SCENARIO 5: Remove Users from Tenant**

**Tester Login:** Tenant Admin

#### 5.1 Remove Member User
- [ ] Find a member user (not admin, not yourself)
- [ ] Click "Remove" button
- [ ] Verify confirmation dialog appears
- [ ] Verify dialog title: "Remove User"
- [ ] Verify dialog has STRONG warning about immediate access loss
- [ ] Verify dialog includes user email
- [ ] Click "Cancel" → Verify nothing happens, dialog closes
- [ ] Click "Remove" button again
- [ ] Click "Confirm"
- [ ] Verify processing state
- [ ] Verify success toast: "Removed {email} from tenant"
- [ ] Verify user immediately disappears from list
- [ ] Click "Refresh" → Verify user still gone
- [ ] Refresh entire page → Verify user doesn't reappear
- [ ] Check database → Verify membership.status = 'removed' OR record deleted

#### 5.2 Remove Admin User
- [ ] Find an admin user (not yourself, not last owner)
- [ ] Click "Remove"
- [ ] Confirm removal
- [ ] Verify removal succeeds
- [ ] Verify admin removed from tenant

#### 5.3 Protected Removal - Self Removal
- [ ] Try to remove yourself (the currently logged-in admin)
- [ ] System should either:
  - Prevent the action entirely (remove button disabled), OR
  - Show strong warning confirmation
- [ ] If allowed, verify consequences are clear
- [ ] If prevented, verify helpful message explains why

#### 5.4 Protected Removal - Last Owner
- [ ] Identify the last/only owner in tenant
- [ ] Try to remove that owner
- [ ] Verify error: "Cannot remove last owner"
- [ ] Verify owner remains in tenant
- [ ] Verify protection is enforced

**Expected:** User removal works with proper safeguards and data integrity

---

### **SCENARIO 6: Multi-Tenant Testing**

**Tester Login:** Platform Admin with access to multiple tenants

#### 6.1 Tenant Switching
- [ ] Verify tenant switcher component visible
- [ ] Click tenant switcher dropdown
- [ ] Verify list of all accessible tenants appears
- [ ] Note users displayed in current tenant
- [ ] Switch to Tenant A
- [ ] Verify URL/context updates
- [ ] Verify tenant ID displays correctly in header
- [ ] Verify user list refreshes automatically
- [ ] Note the users (should be different)
- [ ] Switch to Tenant B
- [ ] Verify different user list appears
- [ ] Verify tenant ID changes in header

#### 6.2 Cross-Tenant Data Isolation
- [ ] In Tenant A: Note current users
- [ ] In Tenant A: Create invitation for `tenantA_user@test.com`
- [ ] Verify invitation creates successfully
- [ ] Switch to Tenant B
- [ ] Verify `tenantA_user@test.com` does NOT appear in Tenant B users
- [ ] Verify user lists are completely separate
- [ ] In Tenant A: Suspend user `userA@example.com`
- [ ] Switch to Tenant B
- [ ] Verify suspension does NOT affect any Tenant B user
- [ ] Verify no data leakage between tenants

#### 6.3 Multi-Tenant Role Verification
- [ ] In Tenant A: Note your role (could be admin)
- [ ] In Tenant B: Note your role (could be member)
- [ ] Verify permissions match role in each tenant
- [ ] If member in Tenant B: Verify cannot manage users there
- [ ] If admin in Tenant A: Verify can manage users there

**Expected:** Complete tenant isolation with no cross-tenant data visibility

---

### **SCENARIO 7: Permission Boundaries & Authorization**

#### 7.1 Regular Member Access Denial
- [ ] Logout from admin
- [ ] Login as regular member (role: "member", no admin privileges)
- [ ] Try navigating to `/admin` or admin dashboard URL directly
- [ ] Verify **access denied** page/message displays
- [ ] Verify message states: "Only tenant admins and platform administrators can manage users"
- [ ] Verify message shows current role: "Your current role: member"
- [ ] Verify page shows lock icon or access denied indicator
- [ ] Verify no user list visible
- [ ] Verify no "Invite User" button visible
- [ ] Try accessing other admin-only routes → Verify all blocked

#### 7.2 Tenant Admin Boundaries
- [ ] Login as Tenant A admin (not platform admin)
- [ ] Verify you CAN access Tenant A admin dashboard
- [ ] Verify you CAN manage Tenant A users
- [ ] **URL Manipulation Test:** Manually change URL to Tenant B ID
- [ ] Try: `/tenants/{TENANT_B_ID}/users` or equivalent
- [ ] Verify 403 Forbidden error OR redirect
- [ ] Verify cannot see Tenant B users
- [ ] Verify platform admin features/badges NOT visible

#### 7.3 Platform Admin vs Tenant Admin Permissions
- [ ] Login as Platform Admin
- [ ] Verify "Platform Admin" badge displays
- [ ] Verify can access ALL tenants via switcher
- [ ] Verify can manage users in any tenant
- [ ] Login as Tenant Admin (not platform admin)
- [ ] Verify NO "Platform Admin" badge
- [ ] Verify tenant switcher shows ONLY accessible tenants
- [ ] Verify cannot access other tenants

**Expected:** Authorization rules strictly enforced, no privilege escalation possible

---

### **SCENARIO 8: Error Handling & Recovery**

#### 8.1 Network Error Simulation
- [ ] Open browser DevTools → Network tab
- [ ] **STOP the backend server** (Ctrl+C in terminal)
- [ ] In UI: Try suspending a user
- [ ] Verify error toast appears with network error message
- [ ] Verify "Operation Failed" banner appears at top
- [ ] Verify error message is clear and actionable
- [ ] Verify operation details shown: "suspend {email}"
- [ ] Verify user status does NOT change in UI
- [ ] **START the backend server again**
- [ ] Wait for server to be ready
- [ ] Click "Retry" button in failed operation banner
- [ ] Verify operation now completes successfully
- [ ] Verify success toast appears
- [ ] Verify user status updates correctly
- [ ] Verify failed operation banner disappears

#### 8.2 Failed Operation Banner Management
- [ ] Trigger a failed operation (stop backend, try any action)
- [ ] Verify failed operation banner displays
- [ ] Verify error details are clear
- [ ] Click "Dismiss" button
- [ ] Verify banner hides immediately
- [ ] Trigger another failed operation
- [ ] Verify new banner replaces old one (or stacks appropriately)

#### 8.3 API Validation Errors
- [ ] Try inviting with empty email → Verify clear validation message
- [ ] Try inviting duplicate user → Verify "already exists" error
- [ ] Try changing role to invalid value (via DevTools manipulation)
- [ ] Verify backend validation catches it
- [ ] Verify error message displays in UI
- [ ] Try removing last owner → Verify "Cannot remove last owner" error
- [ ] Verify all errors are user-friendly, not raw stack traces

#### 8.4 Slow Network Handling
- [ ] Open DevTools → Network tab → Set throttling to "Slow 3G"
- [ ] Perform any action (invite, suspend, role change)
- [ ] Verify loading state shows immediately
- [ ] Verify button disables during request
- [ ] Verify loading spinner/indicator visible
- [ ] Verify UI prevents duplicate submissions
- [ ] Wait for request to complete
- [ ] Verify success feedback shows
- [ ] Reset network to "No throttling"

**Expected:** Robust error handling with clear feedback and recovery options

---

### **SCENARIO 9: UI/UX Quality Assurance**

#### 9.1 Loading States
- [ ] Trigger user list load → Verify "Loading..." message
- [ ] Trigger any action → Verify button shows loading state
- [ ] Verify loading spinner displays
- [ ] Verify disabled state during processing
- [ ] Verify no duplicate actions possible while loading
- [ ] Verify loading doesn't block other UI interactions unnecessarily

#### 9.2 Empty States
- [ ] Apply search filter that returns 0 results
- [ ] Verify helpful empty state message: "No users found"
- [ ] Verify empty state suggests clearing filters
- [ ] Create a new tenant with 0 users
- [ ] Verify empty state message: "No users yet" or similar
- [ ] Verify "Invite User" CTA prominently displayed

#### 9.3 Success & Error Feedback
- [ ] Verify all success actions show toast notifications
- [ ] Verify toasts auto-dismiss after ~3 seconds
- [ ] Verify toasts don't block critical UI
- [ ] Verify error toasts persist longer or require dismissal
- [ ] Verify toast messages are actionable and clear
- [ ] Verify confirmation dialogs require explicit user choice

#### 9.4 Responsive Design
- [ ] Resize browser to 1920px width → Verify layout optimal
- [ ] Resize browser to 1024px width → Verify layout adapts
- [ ] Resize browser to 768px (tablet) → Verify readable
- [ ] Resize browser to 375px (mobile) → Verify usable
- [ ] Verify table becomes scrollable or stacks on mobile
- [ ] Verify buttons remain accessible
- [ ] Verify modals display correctly on small screens
- [ ] Verify no horizontal scroll on any screen size

#### 9.5 Accessibility (WCAG Basics)
- [ ] **Keyboard Navigation:** Tab through all interactive elements
- [ ] Verify focus indicators clearly visible
- [ ] Verify can activate buttons with Enter/Space
- [ ] Verify can close modals with Escape key
- [ ] Verify can navigate dropdowns with arrow keys
- [ ] **Screen Reader Labels:** Inspect elements for `aria-label`
- [ ] Verify form inputs have proper labels
- [ ] Verify buttons have descriptive text
- [ ] Verify status changes announced (inspect `aria-live`)
- [ ] **Color Contrast:** Use browser DevTools to check contrast ratios
- [ ] Verify text readable on all backgrounds
- [ ] Verify status badges have sufficient contrast

**Expected:** Professional UI/UX with good accessibility and responsiveness

---

### **SCENARIO 10: Full User Lifecycle (End-to-End)**

**Complete user journey from invitation to removal**

#### Step-by-Step Flow

1. **Invite New User**
   - [ ] Login as Tenant Admin
   - [ ] Invite `lifecycle@test.com` with "Member" role
   - [ ] Verify invitation success
   - [ ] Note invitation token from logs/database
   - [ ] Logout

2. **Accept Invitation**
   - [ ] Navigate to invitation URL: `/invite/{token}`
   - [ ] Verify invitation preview page loads
   - [ ] Verify tenant name displays
   - [ ] Verify role displays: "Member"
   - [ ] Click "Accept Invitation"
   - [ ] Complete signup/registration
   - [ ] Verify redirect to application
   - [ ] Verify new user can access permitted pages

3. **Verify New User in List**
   - [ ] Login as Tenant Admin
   - [ ] Navigate to admin dashboard
   - [ ] Verify `lifecycle@test.com` appears in user list
   - [ ] Verify role shows "Member"
   - [ ] Verify status shows "Active"

4. **Promote to Admin**
   - [ ] As Tenant Admin: Change `lifecycle@test.com` role to "Admin"
   - [ ] Verify success
   - [ ] Logout

5. **Verify Admin Access**
   - [ ] Login as `lifecycle@test.com`
   - [ ] Navigate to `/admin`
   - [ ] Verify admin dashboard now ACCESSIBLE
   - [ ] Verify can see user list
   - [ ] Verify can invite users
   - [ ] Logout

6. **Suspend User**
   - [ ] Login as original Tenant Admin
   - [ ] Suspend `lifecycle@test.com`
   - [ ] Verify suspension success
   - [ ] Logout

7. **Verify Suspension Enforced**
   - [ ] Try logging in as `lifecycle@test.com`
   - [ ] Verify login BLOCKED
   - [ ] Verify clear error message

8. **Unsuspend User**
   - [ ] Login as Tenant Admin
   - [ ] Unsuspend `lifecycle@test.com`
   - [ ] Verify success
   - [ ] Logout

9. **Verify Access Restored**
   - [ ] Login as `lifecycle@test.com`
   - [ ] Verify login WORKS
   - [ ] Verify can access admin dashboard
   - [ ] Logout

10. **Demote to Member**
    - [ ] Login as Tenant Admin
    - [ ] Change `lifecycle@test.com` role to "Member"
    - [ ] Verify success
    - [ ] Logout

11. **Verify Member Permissions**
    - [ ] Login as `lifecycle@test.com`
    - [ ] Try accessing `/admin`
    - [ ] Verify access DENIED
    - [ ] Verify can access member-allowed pages
    - [ ] Logout

12. **Remove from Tenant**
    - [ ] Login as Tenant Admin
    - [ ] Remove `lifecycle@test.com` from tenant
    - [ ] Verify success
    - [ ] Verify user disappears from list

13. **Verify Complete Removal**
    - [ ] Try logging in as `lifecycle@test.com`
    - [ ] Verify no tenant access OR appropriate error
    - [ ] Verify user cannot access any tenant pages

**Expected:** Complete lifecycle works smoothly with all state transitions functioning correctly

---

## ✅ Success Criteria

### Functional Completeness
- ✅ All user management actions work: invite, role change, suspend, unsuspend, remove
- ✅ User list displays correctly with all fields
- ✅ Search, filter, sort, pagination all function properly
- ✅ Multi-tenant isolation verified

### Permission & Security
- ✅ Authorization properly enforced (admin/member boundaries)
- ✅ Platform admin and tenant admin permissions correct
- ✅ Protected actions blocked: last owner, self-removal
- ✅ Cross-tenant access prevented

### Data Integrity
- ✅ All changes persist after page refresh
- ✅ Database state matches UI state
- ✅ No data corruption or orphaned records
- ✅ Concurrent operations handled correctly

### User Experience
- ✅ Clear, actionable feedback for all operations
- ✅ Confirmation dialogs for destructive actions
- ✅ Loading states visible during operations
- ✅ Error messages clear and helpful
- ✅ Retry mechanism works when operations fail
- ✅ Empty states guide users appropriately

### Error Handling
- ✅ Network errors handled gracefully
- ✅ Validation errors displayed clearly
- ✅ Failed operations can be retried
- ✅ No unhandled exceptions in console

### UI/UX Quality
- ✅ Responsive design works on mobile, tablet, desktop
- ✅ Keyboard navigation functional
- ✅ Basic accessibility requirements met
- ✅ No visual glitches or layout breaks
- ✅ Professional appearance

---

## 📝 Test Execution Guidelines

### Before Testing
1. **Backup database** in case testing creates unexpected data
2. **Clear browser cache** to avoid stale state
3. **Open DevTools** and monitor Console and Network tabs
4. **Prepare test accounts** with correct roles in multiple tenants

### During Testing
1. **Test systematically** - Complete each scenario before moving to next
2. **Document issues** - Screenshot bugs, note steps to reproduce
3. **Check backend logs** for errors even if UI looks okay
4. **Verify database** after critical operations
5. **Test edge cases** - Empty inputs, special characters, max lengths

### Issue Documentation Template

Issue: [Brief description]
Scenario: [Which test scenario]
Steps to Reproduce:

[Step 1]
[Step 2]
[Expected vs Actual]
Screenshots: [Attach]
Error Messages: [From console or UI]
Priority: [High/Medium/Low]


### After Testing
1. **Tally results** - Count passed/failed scenarios
2. **Categorize issues** - Critical bugs vs. enhancement requests
3. **Update checklist** in `current_stage_priority_todo.md`
4. **Report findings** to team
5. **Create bugfix tickets** for critical issues

---

## 🔧 Common Issues & Troubleshooting

### Issue: "Token expired" errors
- **Cause:** JWT token expired during testing
- **Fix:** Logout and login again to get fresh token

### Issue: Users not appearing in list
- **Cause:** Wrong tenant selected, or filter applied
- **Fix:** Check tenant switcher, clear all filters

### Issue: "Cannot remove last owner"
- **Cause:** Protection working as intended
- **Fix:** Create another owner before testing removal

### Issue: Email not sending
- **Cause:** SES not configured or in sandbox mode
- **Fix:** Check backend logs, verify SES settings

### Issue: Suspension not blocking login
- **Cause:** Cognito sync delay or logic issue
- **Fix:** Check `user.is_active` field in database, verify suspension endpoint

---

## 📊 Test Progress Tracking

| Scenario | Status | Issues Found | Notes |
|----------|--------|--------------|-------|
| 1. Platform Admin Access | [ ] | | |
| 2. Invite New User | [ ] | | |
| 3. Change User Roles | [ ] | | |
| 4. Suspend & Unsuspend | [ ] | | |
| 5. Remove Users | [ ] | | |
| 6. Multi-Tenant Testing | [ ] | | |
| 7. Permission Boundaries | [ ] | | |
| 8. Error Handling | [ ] | | |
| 9. UI/UX Quality | [ ] | | |
| 10. Full User Lifecycle | [ ] | | |

**Legend:** ✅ Pass | ❌ Fail | ⚠️ Partial | ⏭️ Skipped

---

## 🎓 Testing Best Practices

1. **Think like a user** - Don't just test happy paths
2. **Be evil** - Try to break things intentionally
3. **Test boundaries** - Empty inputs, max values, special characters
4. **Check both UI and API** - UI might lie, always verify backend
5. **Test concurrency** - What if two admins modify same user?
6. **Mobile matters** - Don't just test on desktop
7. **Accessibility counts** - Keyboard and screen reader users exist
8. **Document everything** - Future you will thank present you

---

**End of Test Plan**
### After Testing
1. **Tally results** - Count passed/failed scenarios
2. **Categorize issues** - Critical bugs vs. enhancement requests
3. **Update checklist** in `current_stage_priority_todo.md`
4. **Report findings** to team
5. **Create bugfix tickets** for critical issues

---

## 🔧 Common Issues & Troubleshooting

### Issue: "Token expired" errors
- **Cause:** JWT token expired during testing
- **Fix:** Logout and login again to get fresh token

### Issue: Users not appearing in list
- **Cause:** Wrong tenant selected, or filter applied
- **Fix:** Check tenant switcher, clear all filters

### Issue: "Cannot remove last owner"
- **Cause:** Protection working as intended
- **Fix:** Create another owner before testing removal

### Issue: Email not sending
- **Cause:** SES not configured or in sandbox mode
- **Fix:** Check backend logs, verify SES settings

### Issue: Suspension not blocking login
- **Cause:** Cognito sync delay or logic issue
- **Fix:** Check `user.is_active` field in database, verify suspension endpoint

---

## 📊 Test Progress Tracking

| Scenario | Status | Issues Found | Notes |
|----------|--------|--------------|-------|
| 1. Platform Admin Access | [ ] | | |
| 2. Invite New User | [ ] | | |
| 3. Change User Roles | [ ] | | |
| 4. Suspend & Unsuspend | [ ] | | |
| 5. Remove Users | [ ] | | |
| 6. Multi-Tenant Testing | [ ] | | |
| 7. Permission Boundaries | [ ] | | |
| 8. Error Handling | [ ] | | |
| 9. UI/UX Quality | [ ] | | |
| 10. Full User Lifecycle | [ ] | | |

**Legend:** ✅ Pass | ❌ Fail | ⚠️ Partial | ⏭️ Skipped

---

## 🎓 Testing Best Practices

1. **Think like a user** - Don't just test happy paths
2. **Be evil** - Try to break things intentionally
3. **Test boundaries** - Empty inputs, max values, special characters
4. **Check both UI and API** - UI might lie, always verify backend
5. **Test concurrency** - What if two admins modify same user?
6. **Mobile matters** - Don't just test on desktop
7. **Accessibility counts** - Keyboard and screen reader users exist
8. **Document everything** - Future you will thank present you

---

**End of Test Plan**