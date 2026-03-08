# Priority 2 Manual Test Scenarios

Date: 2026-03-08
Purpose: Manual verification checklist for Priority 2 Admin UI completion

## Prerequisites

1. Backend running: `cd backend; uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
2. Frontend running: `cd frontend; npm run dev`
3. At least 2 users exist:
   - User A: Admin or platform_admin
   - User B: Member
4. At least 2 tenants exist (for multi-tenant testing)

---

## Test Scenario 1: Admin Dashboard Access

### Test 1.1: Admin Can Access Dashboard
**Steps:**
1. Log in as User A (admin)
2. Navigate to home page
3. Click "Admin Dashboard" link in header

**Expected:**
- ✅ Dashboard link visible
- ✅ Page loads successfully
- ✅ Shows "User Management" title
- ✅ Shows "Platform Admin" badge if applicable
- ✅ Shows "Invite User" button
- ✅ Shows UserList component with search/filter/sort

### Test 1.2: Member Cannot Access Dashboard
**Steps:**
1. Log in as User B (member)
2. Navigate to home page
3. Check header navigation

**Expected:**
- ✅ "Admin Dashboard" link NOT visible
- ✅ If manually navigate to `/admin`, shows "Access Denied" message
- ✅ Shows current role correctly

---

## Test Scenario 2: User Invitation Flow

### Test 2.1: Invite New User
**Steps:**
1. Log in as admin
2. Go to Admin Dashboard
3. Click "Invite User" button
4. Enter email: `test-new-user@example.com`
5. Select role: `member`
6. Click "Send Invitation"

**Expected:**
- ✅ Modal appears with clean UI
- ✅ Email validation works (shows error for invalid emails)
- ✅ Success toast appears
- ✅ Modal closes
- ✅ Email sent to address (check backend logs or email)

### Test 2.2: Duplicate Email Prevention
**Steps:**
1. Invite user with email that already exists
2. Submit form

**Expected:**
- ✅ Shows error: "This email is already a member of this tenant"
- ✅ Form does not submit
- ✅ Error clears when email input changes

### Test 2.3: Permission Check
**Steps:**
1. Log in as member
2. Try to access invite functionality

**Expected:**
- ✅ "Invite User" button not visible
- ✅ If accessed programmatically, backend returns 403

---

## Test Scenario 3: User List Features

### Test 3.1: Search Functionality
**Steps:**
1. Go to Admin Dashboard
2. Type in search box: partial email or name

**Expected:**
- ✅ List filters in real-time
- ✅ Matches email and name fields
- ✅ Case-insensitive search
- ✅ Shows "No matching users" if none found

### Test 3.2: Role Filter
**Steps:**
1. Select "Admin" from role filter
2. Verify only admins shown
3. Select "Member"
4. Select "All Roles"

**Expected:**
- ✅ Filters work correctly
- ✅ Pagination updates correctly
- ✅ Count reflects filtered results

### Test 3.3: Status Filter (Platform Admin Only)
**Steps:**
1. Log in as platform_admin
2. Use status filter (Active/Suspended/All)

**Expected:**
- ✅ Filter works correctly
- ✅ Shows suspended users with red "Suspended" text

### Test 3.4: Column Sorting
**Steps:**
1. Click "Email" column header
2. Click again
3. Click "Name" header
4. Click "Role" header

**Expected:**
- ✅ First click: ascending (▲)
- ✅ Second click: descending (▼)
- ✅ Sorts data correctly
- ✅ Pagination preserved/reset appropriately

### Test 3.5: Pagination
**Steps:**
1. Change page size to 10, 25, 50
2. Navigate forward/backward with buttons

**Expected:**
- ✅ Correct number of items per page
- ✅ Page indicator updates
- ✅ Previous/Next buttons disabled appropriately
- ✅ Shows "Showing X-Y of Z" correctly

### Test 3.6: Mobile Responsive View
**Steps:**
1. Resize browser to < 768px width
2. Check user list display

**Expected:**
- ✅ Switches to card layout
- ✅ All actions still accessible
- ✅ Role selector still works
- ✅ Remove/Suspend buttons visible

---

## Test Scenario 4: User Management Actions

### Test 4.1: Change User Role
**Steps:**
1. As admin, select a different role for a user
2. Confirm change

**Expected:**
- ✅ Role dropdown appears for each user (except current user)
- ✅ Change triggers immediately
- ✅ Success toast appears
- ✅ User list refreshes showing new role
- ✅ Cannot change own role (dropdown disabled)

### Test 4.2: Remove User
**Steps:**
1. As admin, click "Remove" on a user
2. Read confirmation dialog
3. Click "Remove"

**Expected:**
- ✅ Confirmation dialog appears
- ✅ Shows user email in message
- ✅ Dialog has danger styling (red)
- ✅ On confirm: success toast
- ✅ User removed from list
- ✅ Cannot remove self (button not visible)

### Test 4.3: Remove User - Cancellation
**Steps:**
1. Click "Remove" on a user
2. Click "Cancel" in dialog

**Expected:**
- ✅ Dialog closes
- ✅ No action taken
- ✅ User still in list

### Test 4.4: Remove User - Error Retry
**Steps:**
1. Temporarily stop backend server
2. Try to remove user
3. Check retry mechanism
4. Restart backend
5. Click "Retry"

**Expected:**
- ✅ Error toast appears
- ✅ Yellow retry banner appears with error details
- ✅ Shows "Retry" and "Dismiss" buttons
- ✅ Retry button re-executes removal
- ✅ Success after backend restored

### Test 4.5: Suspend User (Platform Admin Only)
**Steps:**
1. Log in as platform_admin
2. Click "Suspend" on an active user
3. Confirm

**Expected:**
- ✅ Suspend button visible only to platform_admin
- ✅ Confirmation dialog appears
- ✅ On confirm: user suspended
- ✅ Account status changes to "Suspended" (red)
- ✅ Button changes to "Unsuspend"

### Test 4.6: Unsuspend User (Platform Admin Only)
**Steps:**
1. Click "Unsuspend" on a suspended user
2. Confirm

**Expected:**
- ✅ Confirmation dialog appears
- ✅ On confirm: user unsuspended
- ✅ Account status changes to "Active" (green)
- ✅ Button changes to "Suspend"

---

## Test Scenario 5: Multi-Tenant Scenarios

### Test 5.1: Tenant Isolation
**Steps:**
1. Create users in Tenant A
2. Create users in Tenant B
3. Log in as admin of Tenant A
4. View Admin Dashboard

**Expected:**
- ✅ Only shows users from Tenant A
- ✅ Cannot see users from Tenant B

### Test 5.2: Tenant Switching
**Steps:**
1. Log in as user with membership in 2+ tenants
2. Switch tenant using TenantSwitcher
3. Check Admin Dashboard

**Expected:**
- ✅ UserList refreshes automatically
- ✅ Shows users for new tenant
- ✅ Permissions re-evaluated for new tenant context

### Test 5.3: Platform Admin Across Tenants
**Steps:**
1. Log in as platform_admin
2. Switch between tenants
3. Perform admin actions in each

**Expected:**
- ✅ Can see users in all tenants
- ✅ Can suspend/unsuspend in any tenant
- ✅ Platform Admin badge always visible

---

## Test Scenario 6: Error Handling & Edge Cases

### Test 6.1: Network Error Handling
**Steps:**
1. Disconnect network or stop backend
2. Try to load users
3. Try to invite user
4. Try to remove user

**Expected:**
- ✅ Clear error messages
- ✅ No crashes
- ✅ Retry mechanism available where applicable

### Test 6.2: Empty States
**Steps:**
1. Create tenant with no users (or use filters to show none)
2. Check display

**Expected:**
- ✅ Shows "No matching users" message
- ✅ Search/filter controls still visible
- ✅ "Invite User" button still accessible

### Test 6.3: Loading States
**Steps:**
1. Click "Refresh" button
2. Observe table during loading

**Expected:**
- ✅ Shows loading indicator
- ✅ Buttons disabled during load
- ✅ Table slightly dimmed (opacity)

---

## Test Scenario 7: Accessibility

### Test 7.1: Keyboard Navigation
**Steps:**
1. Use Tab key to navigate through page
2. Use Enter to activate buttons
3. Use Escape to close modals

**Expected:**
- ✅ Focus visible on all interactive elements
- ✅ Logical tab order
-✅ Enter activates buttons
- ✅ Escape closes confirmation dialogs and modals

### Test 7.2: Screen Reader Labels
**Steps:**
1. Inspect elements with dev tools
2. Check aria-label attributes

**Expected:**
- ✅ All buttons have descriptive aria-labels
- ✅ Search input has aria-label
- ✅ Filter dropdowns have aria-labels
- ✅ Table has proper ARIA sorting indicators

---

## Completion Checklist

After running all scenarios:

- [ ] All admin dashboard features work correctly
- [ ] Permission enforcement verified
- [ ] Multi-tenant isolation confirmed
- [ ] Error handling and retry work
- [ ] Mobile responsive layout verified
- [ ] Accessibility features tested
- [ ] No JavaScript errors in console
- [ ] No network errors (except intentional tests)

---

## Schema Change Notes

Document any schema changes needed:

- [ ] None discovered during testing
- [ ] (Add findings here)

**This section feeds into Priority 1 (RDS migration tomorrow).**

---

## Next Steps After Manual Testing

1. Document any bugs found
2. Fix critical issues
3. Note any schema changes needed before RDS migration
4. Update verification report with final status
