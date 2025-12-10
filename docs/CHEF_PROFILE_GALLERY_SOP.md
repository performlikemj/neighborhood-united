# Chef Profile & Gallery - Standard Operating Procedure

## Overview

The **Profile & Gallery** features in Chef Hub allow chefs to manage their public-facing presence on the sautai platform. A well-crafted profile and photo gallery help attract customers and showcase your culinary expertise.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Profile Management](#profile-management)
3. [Photo Gallery](#photo-gallery)
4. [Break Mode](#break-mode)
5. [Stripe Connect Setup](#stripe-connect-setup)
6. [Public Profile](#public-profile)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Potential customers need to:
- Learn about your cooking style
- See examples of your work
- Understand your experience
- Feel confident in booking you

### The Solution
Profile & Gallery provides professional presentation tools:
- **Profile** - Bio, experience, and service information
- **Photos** - Visual portfolio of your culinary work
- **Break Mode** - Manage availability professionally
- **Stripe** - Secure payment setup

---

## Profile Management

### Accessing Profile Settings
1. Log in to Chef Hub
2. Click **"Profile"** in the left sidebar
3. You'll see your profile editing panel

![Profile Editing Page](./screenshots/profile-editing-page.png)
*The Profile editing panel with all editable fields*

### Profile Elements

The profile editing panel contains the following fields:

#### Experience Field
Share your culinary background:
- Placeholder text: *"Share your culinary experience…"*
- Examples: "10+ years", "Former restaurant chef", "Culinary school graduate"

#### Bio Field
Your professional story (larger text area):
- Placeholder text: *"Tell customers about your style and specialties…"*
- Include: who you are, cooking philosophy, specialties, training/background

**Tips for a great bio:**
- Keep it personal but professional
- Mention certifications
- Highlight specialties
- Include your "why"

#### Profile Picture
Your primary identification photo:
- **Recommended**: Professional headshot
- **Size**: At least 400x400 pixels
- **Format**: JPG, PNG

To upload:
1. Click **"Choose file"** button (first file input)
2. Select image file
3. Preview appears
4. Click **"Save changes"** to apply

#### Banner Image
Large header image on your public profile:
- **Recommended**: Cooking action shot or signature dish
- **Size**: At least 1200x400 pixels
- **Format**: JPG, PNG

To upload:
1. Click **"Choose file"** button (second file input)
2. Select image file
3. Preview appears
4. Click **"Save changes"** to apply

#### Calendly URL (Optional)
Link your booking calendar for consultations:
- Placeholder: *"https://calendly.com/yourname/consultation"*
- Allows customers to book directly with you

#### Service Areas
Manage locations where you provide service:
- View your current approved service areas
- Click **"+ Request New Area"** to add new locations
- Use **"Cancel"** button to remove pending requests

![Service Areas Section](./screenshots/profile-service-areas.png)
*Service area management with request functionality*

### Saving Changes
1. Make your edits to any field
2. Click **"Save changes"** button
3. Wait for confirmation
4. Changes are live immediately

---

## Photo Gallery

### Accessing Photo Management
1. Log in to Chef Hub
2. Click **"Photos"** in the left sidebar
3. You'll see the photo upload form and your gallery below

![Photos Gallery Page](./screenshots/photos-gallery-page.png)
*The Photos section showing upload form and existing gallery*

### Uploading Photos

The upload form contains:

1. **Image Upload** (required)
   - Click **"Choose file"** button
   - Select your photo from your device
   
2. **Title** (optional text field)
   - Name for the photo
   - Example: "Seared Salmon with Citrus Glaze"

3. **Caption** (optional text field)
   - Additional description
   - Example: "Fresh Atlantic salmon with seasonal vegetables"

4. **Featured Checkbox**
   - Check to highlight this photo
   - Featured photos appear prominently on your profile

5. Click **"Upload"** button to save

### Managing Photos

#### Your Gallery
- Located below the upload form under **"Your gallery"** heading
- Photos display in a responsive grid
- Most recent first by default
- Featured photos may appear first

#### Delete a Photo
1. Find the photo in your gallery grid
2. Click the **"Delete"** button on that photo
3. Photo is removed immediately

### Photo Best Practices

**What to Photograph**
- ✓ Finished dishes (plated beautifully)
- ✓ Cooking action shots
- ✓ Fresh ingredients
- ✓ Kitchen setup
- ✓ Happy customers (with permission)

**Technical Tips**
- Use good lighting (natural preferred)
- Clean background
- Sharp focus
- Proper white balance
- High resolution

**What to Avoid**
- ✗ Blurry images
- ✗ Poor lighting
- ✗ Cluttered backgrounds
- ✗ Stock photos
- ✗ Copyrighted content

---

## Break Mode

### What Is Break Mode?
Break mode lets you temporarily pause your chef activities:
- No new events can be created
- Upcoming events are cancelled
- Orders are refunded
- You remain visible but marked as unavailable

### When to Use Break Mode
- Vacation/travel
- Personal time off
- Health reasons
- Seasonal break
- Temporary capacity limits

### Accessing Break Mode

1. Go to **Dashboard** in the left sidebar
2. The Break Mode toggle is displayed in the main content area

![Dashboard Break Mode](./screenshots/dashboard-break-mode.png)
*The Dashboard showing Break Mode toggle and optional note field*

### Enabling Break Mode

1. Go to **Dashboard** tab
2. Find the toggle switch (shows **"Off"** when inactive)
3. Optionally enter a note in the **"Optional note for your guests"** field
4. Click/toggle the switch to turn it **On**

**What happens:**
- All future events are cancelled
- Pending orders are refunded
- Customers are notified
- Your profile shows "On Break"

### Disabling Break Mode

1. Go to **Dashboard** tab
2. Click/toggle the switch back to **Off**

**What happens:**
- You can create events again
- Customers can book services
- Profile returns to normal

### Break Mode Best Practices

**1. Plan Ahead**
- Complete existing orders first
- Communicate with scheduled customers
- Set clear return date

**2. Use Reason Field**
- "On vacation until Dec 15"
- "Taking seasonal break"
- "Back in the new year"

**3. Communicate**
- Message active clients before enabling
- Post on social media
- Set expectations for return

---

## Stripe Connect Setup

### Why Stripe Connect?
Stripe enables you to:
- Accept payments professionally
- Receive direct deposits
- Process refunds
- Track revenue

### Setup Process

1. Go to **Dashboard** tab
2. Find **"Stripe Connect"** section
3. Click **"Complete Stripe Onboarding"**
4. Follow Stripe's verification process:
   - Personal information
   - Business details
   - Bank account
   - Identity verification

### Stripe Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| **Not Started** | No account created | Start onboarding |
| **Pending** | Verification in progress | Wait or continue |
| **Active** | Ready to accept payments | None needed |
| **Restricted** | Issues need attention | Fix problems |

### Fixing Issues

If your account is restricted:
1. Click **"Fix Account Issues"**
2. Complete required verification steps
3. Re-verify when prompted

### After Setup
Once Stripe is active:
- Payment Links become available
- Service orders can be paid
- Refunds can be processed
- Revenue is deposited automatically

---

## Public Profile

### Viewing Your Public Profile

From the **Profile** section in Chef Hub:
1. Scroll down to the **"Public preview"** section
2. Click **"View public profile ↗"** link
3. Opens your profile as customers see it (in a new tab)

![Public Profile Preview Link](./screenshots/profile-public-preview.png)
*The Public preview section with link to view your profile*

### Your Public URL
Your profile is accessible at:
```
sautai.com/c/yourusername
```

Or via the chefs directory:
```
sautai.com/chefs
```

### What Customers See

**Profile Header**
- Banner image
- Profile picture
- Name/Username
- Rating (if any)
- Location/Service areas

**About Section**
- Bio
- Experience
- Specialties

**Photo Gallery**
- Your uploaded photos
- Filterable and browsable
- Featured photos highlighted

**Services**
- Available service offerings
- Pricing tiers
- Booking options
- Calendly integration (if configured)

**Meals & Events**
- Upcoming events
- Menu offerings

### Gallery Page
Customers can access your full gallery at:
```
sautai.com/c/yourusername/gallery
```

Features:
- Full-screen viewing
- Filter by tags
- Sort by date
- Share individual photos

![Public Chef Profile](./screenshots/public-chef-profile.png)
*Example of a public chef profile page as seen by customers*

---

## Best Practices

### Profile Optimization

**1. Complete All Fields**
Incomplete profiles appear less professional:
- ✓ Profile picture uploaded
- ✓ Banner image set
- ✓ Bio written
- ✓ Experience listed
- ✓ Service areas defined

**2. Professional Photography**
Invest in quality images:
- Professional headshot (once)
- Food photography basics
- Consistent style

**3. Compelling Bio**
Tell your story:
- Start with a hook
- Include credentials
- Mention specialties
- End with call to action

**4. Regular Updates**
Keep content fresh:
- New photos monthly
- Update seasonal offerings
- Refresh bio annually

### Gallery Strategy

**1. Quantity Matters**
Aim for 10-20 quality photos minimum:
- Shows range
- Builds confidence
- Provides social proof

**2. Variety**
Show different aspects:
- Different cuisines
- Various meal types
- Cooking process
- Final presentations

**3. Featured Photos**
Choose your best 3-5 to feature:
- Most visually appealing
- Signature dishes
- Best representation of style

**4. Seasonal Content**
Add seasonal photos:
- Holiday meals
- Summer BBQ
- Fall comfort food
- Spring fresh dishes

---

## Troubleshooting

### Profile picture not updating

**Causes**:
- File too large
- Wrong format
- Browser cache

**Solutions**:
1. Resize to under 5MB
2. Use JPG or PNG
3. Clear browser cache
4. Try incognito mode

### Banner image looks cropped

**Cause**: Image dimensions don't match expected ratio.

**Solution**:
1. Use 3:1 ratio (e.g., 1200x400)
2. Center important content
3. Test on mobile view

### Photos not appearing in gallery

**Causes**:
- Upload not completed
- Processing delay
- Format not supported

**Solutions**:
1. Wait a few minutes
2. Refresh the page
3. Try re-uploading
4. Use standard JPG/PNG

### Stripe onboarding stuck

**Causes**:
- Verification pending
- Missing information
- Document issues

**Solutions**:
1. Check email for Stripe messages
2. Log in to Stripe directly
3. Complete any pending steps
4. Contact Stripe support if stuck

### Break mode didn't cancel events

**Cause**: Processing error or timeout.

**Solutions**:
1. Check events list manually
2. Cancel remaining events individually
3. Contact support for refund help

---

## Technical Details

### Data Models

```python
ChefProfile:
    user                    # FK to User
    bio                     # Text biography
    experience              # Experience description
    profile_pic             # Image field
    banner_image            # Image field
    service_areas           # M2M to PostalCode
    is_on_break             # Break mode status
    break_reason            # Optional reason
    stripe_account_id       # Stripe Connect ID
    created_at              # Creation timestamp
    updated_at              # Last update

ChefPhoto:
    chef                    # FK to Chef
    image                   # Image file
    thumbnail               # Generated thumbnail
    title                   # Photo title
    caption                 # Photo caption
    tags                    # JSON array
    is_featured             # Featured flag
    created_at              # Upload timestamp
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chefs/api/me/chef/profile/` | GET | Get chef profile |
| `/chefs/api/me/chef/profile/` | PATCH | Update profile |
| `/chefs/api/me/chef/break/` | POST | Toggle break mode |
| `/chefs/api/me/photos/` | GET | List photos |
| `/chefs/api/me/photos/` | POST | Upload photo |
| `/chefs/api/me/photos/<id>/` | PATCH | Update photo |
| `/chefs/api/me/photos/<id>/` | DELETE | Delete photo |
| `/chefs/api/public/<id>/` | GET | Public chef profile |
| `/chefs/api/public/by-username/<username>/` | GET | Profile by username |

### Image Requirements

**Profile Picture**
- Min: 200x200 px
- Recommended: 400x400 px
- Max file: 5MB
- Formats: JPG, PNG

**Banner Image**
- Min: 800x300 px
- Recommended: 1200x400 px
- Max file: 10MB
- Formats: JPG, PNG

**Gallery Photos**
- Recommended: 1200x800 px or larger
- Max file: 10MB
- Formats: JPG, PNG, WebP

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with gallery and break mode |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

