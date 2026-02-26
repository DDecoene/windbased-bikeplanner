# Address Autocomplete Fix - Test Plan

## Test Environment
- URL: https://localhost
- Browser: Chrome/Safari/Firefox
- Backend: Running locally via Docker

## Test Scenarios

### 1. **Autocomplete Search Functionality**
**Steps:**
1. Go to https://localhost
2. Click the "Startadres" (start address) input field
3. Type "grote markt" (3+ characters to trigger search)
4. Wait 300ms for debounce
5. Verify a dropdown list appears with suggestions below the input field

**Expected Results:**
- ✓ Dropdown appears with max 6 address suggestions
- ✓ Each suggestion shows complete address (street, housenumber, postcode, city)
- ✓ Loading spinner appears briefly while fetching
- ✓ Dropdown closes if you clear the input (< 3 chars)

### 2. **Autocomplete Search Selection**
**Steps:**
1. From Test 1, ensure dropdown is visible with suggestions
2. Click on one of the suggestions (e.g., "Grote Markt, Brugge, 8000, Belgié")

**Expected Results:**
- ✓ Address is filled into the input field
- ✓ Dropdown closes immediately after selection
- ✓ Input field remains focused and usable

### 3. **Keyboard Navigation**
**Steps:**
1. Type "bruges" in address input (to get suggestions)
2. Wait for dropdown to appear
3. Press **Down Arrow** - highlight should move down to first suggestion
4. Press **Down Arrow** again - highlight moves to second suggestion
5. Press **Up Arrow** - highlight moves back to first suggestion
6. Press **Escape** - dropdown should close
7. Type again to reopen dropdown
8. Press **Down Arrow** to highlight a suggestion
9. Press **Enter** - suggestion should be selected

**Expected Results:**
- ✓ Down Arrow cycles through suggestions (visual highlight changes)
- ✓ Up Arrow cycles backwards through suggestions
- ✓ Escape closes the dropdown
- ✓ Enter selects the highlighted suggestion
- ✓ Focus remains on input after selection

### 4. **Click Outside Closes Dropdown**
**Steps:**
1. Type "brugge" in address input (to open dropdown)
2. Click somewhere else on the page (e.g., the distance slider or "Afstand" label)

**Expected Results:**
- ✓ Dropdown closes when you click outside the address field
- ✓ The page is still interactive
- ✓ No dropdown appears when you click in empty areas

### 5. **Route Generation With Results Display** ⚠️ CRITICAL TEST
**Steps:**
1. Fill address input with a valid Belgian address (e.g., "Brugge" or "Grote Markt, Brugge")
2. Optionally modify distance (slider)
3. Log in if prompted
4. Click "Genereer Route" button

**Expected Results:**
- ✓ Loading message appears ("Windcondities analyseren...", etc.)
- ✓ Dropdown closes automatically (suggestions hidden)
- ✓ After ~5-30 seconds, THE RED BOX SECTION APPEARS with:
  - Distance stat (AFSTAND)
  - Junction count (KNOOPPUNTEN)
  - Network radius (NETWERK)
  - Wind speed (WINDSNELHEID)
  - Wind direction (RICHTING)
  - Route sequence (ROUTE: XX → YY → ZZ)
  - Download GPX button
  - Share image button
  - Donation section
  - Map below with route drawn

⚠️ **This is the main fix validation**: If results don't appear, the autocomplete is still interfering with rendering.

### 6. **Multiple Route Generations**
**Steps:**
1. Generate a route (from Test 5)
2. Verify results appear
3. Change the address input to a different location
4. The dropdown might appear while typing
5. Click "Genereer Route" again

**Expected Results:**
- ✓ Second route generates successfully
- ✓ Previous route results are cleared and new results appear
- ✓ Dropdown closes on submit
- ✓ No state pollution between requests

### 7. **Logout/Login State**
**Steps:**
1. Generate a route successfully
2. Click the user avatar (top right) and "Sign Out"
3. Address field should reset
4. Dropdown should close if open
5. Try filling address and see if dropdown still works (should work for guests)

**Expected Results:**
- ✓ Address field clears on logout
- ✓ Dropdown clears on logout
- ✓ Autocomplete still works for anonymous users
- ✓ No errors in console

## Browser Console Checks
Open DevTools (F12) and check:
- **No JavaScript errors** in Console
- **No network errors** for https://photon.komoot.io API calls
- **Network tab**: Watch requests to `/api/generate-route` complete successfully

## Success Criteria
✅ **Must Pass:**
- [x] Autocomplete search works and shows suggestions
- [x] Keyboard navigation works (arrow keys, enter, escape)
- [x] Route generation completes WITHOUT autocomplete interfering
- [x] Results section renders completely (red box with all stats)
- [x] Dropdown properly closes on form submit
- [x] Click-outside closes dropdown

❌ **Failure Cases (Stop testing if any occur):**
- Results section doesn't appear after route generation
- Suggestions dropdown covers/hides results
- JavaScript errors in console related to autocomplete
- Keyboard navigation doesn't work
- Route generation fails

## Test Completion
Once all tests pass, the fix is validated and ready to commit.
