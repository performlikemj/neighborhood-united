# Chef Connections Management - Standard Operating Procedure

> ⚠️ **DEPRECATED**: The separate Connections tab has been merged into the **Clients** tab. 
> Please see [CHEF_CLIENT_MANAGEMENT_SOP.md](CHEF_CLIENT_MANAGEMENT_SOP.md) for current documentation.
> 
> Connection management (accept/decline/end) is now available directly in the client detail panel within the Clients tab.

---

## Overview (Legacy Reference)

The **Connections** feature in Chef Hub manages the relationship lifecycle between chefs and customers on the Hood United platform. It handles connection requests, approvals, and ongoing relationship management.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Features](#key-features)
3. [Connection Lifecycle](#connection-lifecycle)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Understanding the Interface](#understanding-the-interface)
6. [Managing Connection Requests](#managing-connection-requests)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Without a structured connection system:
- Anyone could message chefs indiscriminately
- No way to vet potential clients before engaging
- Chefs can't control their workload
- Customer information scattered across channels

### The Solution
Connections provides a professional relationship management system:
- **Controlled Access** - Customers request connection before messaging
- **Vetting Process** - Review requests before accepting
- **Status Tracking** - Clear lifecycle from request to active
- **Clean Endings** - Professionally end relationships when needed

---

## Key Features

### 1. Connection Request Management
- View all incoming connection requests
- Accept or decline with one click
- See customer profile before deciding

### 2. Active Connection Tracking
- List of all connected customers
- Connection duration tracking
- Quick access to customer profiles

### 3. Connection History
- Declined requests
- Ended connections
- Full relationship timeline

### 4. Two-Way Connections
Either party can initiate:
- **Customer → Chef**: Customer discovers chef, requests connection
- **Chef → Customer**: Chef invites existing client to platform

---

## Connection Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                  CONNECTION LIFECYCLE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. REQUEST INITIATED                                      │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Customer: "I'd like to connect with Chef Mike"      │  │
│   │ OR                                                  │  │
│   │ Chef: "I'm inviting Sarah to connect"               │  │
│   └─────────────────────────────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   2. PENDING STATE                                          │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Status: PENDING                                     │  │
│   │ Waiting for: Recipient approval                     │  │
│   │ Actions: Accept | Decline                           │  │
│   └─────────────────────────────────────────────────────┘  │
│                            │                                │
│              ┌─────────────┼─────────────┐                 │
│              ▼             ▼             ▼                 │
│   3a. ACCEPTED         3b. DECLINED   3c. EXPIRED         │
│   ┌──────────────┐     ┌───────────┐  ┌───────────┐       │
│   │ Status:      │     │ Status:   │  │ Status:   │       │
│   │ ACCEPTED     │     │ DECLINED  │  │ EXPIRED   │       │
│   │              │     │           │  │           │       │
│   │ Full access  │     │ No access │  │ No access │       │
│   │ to services  │     │ Can't re- │  │ Can re-   │       │
│   │              │     │ request   │  │ request   │       │
│   └──────────────┘     └───────────┘  └───────────┘       │
│         │                                                  │
│         ▼                                                  │
│   4. ACTIVE RELATIONSHIP                                   │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ • Customer can book services                        │  │
│   │ • Chef can create meal plans                        │  │
│   │ • Both can message                                  │  │
│   │ • Payment links enabled                             │  │
│   └─────────────────────────────────────────────────────┘  │
│         │                                                  │
│         ▼                                                  │
│   5. END CONNECTION (optional)                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Status: ENDED                                       │  │
│   │ • Access removed                                    │  │
│   │ • History preserved                                 │  │
│   │ • Can reconnect later                               │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Access Connections
1. Log in to Chef Hub
2. Click **"Connections"** in the left sidebar
3. You'll see your connections dashboard

### Step 2: Review Pending Requests

#### Viewing Pending Requests
1. Pending requests appear at the top
2. Each request shows:
   - Customer name
   - Request date
   - Who initiated (you or them)
   - Basic profile info

#### Accepting a Request
1. Click **"Accept"** button on the request
2. Connection immediately becomes active
3. Customer gains access to your services
4. They appear in your Clients list

#### Declining a Request
1. Click **"Decline"** button on the request
2. Request is moved to declined list
3. Customer is notified
4. They cannot re-request immediately

### Step 3: View Active Connections

The **Accepted** section shows all active clients:
- Customer name and profile
- Connection date
- Access to view full profile

### Step 4: Invite a Customer

To invite an existing off-platform client:
1. Share your chef profile link: `hoodunited.com/c/yourusername`
2. Customer creates account and requests connection
3. Accept their request
4. They become a platform client

> **Alternative**: Use the Client Management feature to add manual contacts who don't need platform access.

### Step 5: End a Connection

To professionally end a relationship:
1. Find the connection in Accepted list
2. Click **"End Connection"** button
3. Confirm the action
4. Connection moves to Ended list

**What happens when you end a connection:**
- Customer loses access to book services
- Existing orders are not affected
- You can no longer create meal plans for them
- History is preserved
- Either party can reconnect later

---

## Understanding the Interface

### Connection Sections

| Section | Description |
|---------|-------------|
| **Pending** | Awaiting response (from you or customer) |
| **Accepted** | Active connections |
| **Declined** | Requests you declined |
| **Ended** | Connections that were terminated |

### Connection Card Elements

| Element | Description |
|---------|-------------|
| **Avatar** | Customer profile picture |
| **Name** | Customer display name |
| **Username** | @username for profile link |
| **Date** | Connection/request date |
| **Initiated By** | Who sent the request |
| **Actions** | Accept/Decline/End buttons |

### Status Badges

| Badge | Color | Meaning |
|-------|-------|---------|
| **Pending** | Yellow | Awaiting response |
| **Accepted** | Green | Active connection |
| **Declined** | Red | Request declined |
| **Ended** | Gray | Relationship ended |

### Initiated By Indicators

| Indicator | Meaning |
|-----------|---------|
| "You sent this invitation" | You initiated |
| "Customer sent the invitation" | They found you |
| "Chef sent the invitation" | (From customer view) |

---

## Managing Connection Requests

### When to Accept

Accept connection requests when:
- ✓ Customer seems genuinely interested
- ✓ Their dietary needs match your expertise
- ✓ You have capacity for new clients
- ✓ Their location is in your service area

### When to Decline

Consider declining when:
- ✗ You're at capacity
- ✗ Their needs are outside your expertise
- ✗ Location is too far for service
- ✗ Profile seems suspicious

### Response Time Best Practices

| Timeframe | Recommendation |
|-----------|----------------|
| **< 24 hours** | Ideal - shows professionalism |
| **1-3 days** | Acceptable |
| **> 1 week** | May lose interested customers |

### Reconnection Scenarios

**After Decline:**
- Customer cannot immediately re-request
- Cooling-off period applies
- They can find other chefs

**After End:**
- Either party can initiate new connection
- Starts fresh pending request
- Previous history not deleted

---

## Best Practices

### 1. Respond Promptly
- Check pending requests daily
- Quick responses improve your reputation
- Customers may choose other chefs if ignored

### 2. Review Before Accepting
- Check customer profile
- Verify dietary requirements match your skills
- Confirm service area compatibility

### 3. Communicate Declines Professionally
If declining, consider:
- Sending a message explaining why
- Suggesting alternative chefs
- Leaving the door open for future

### 4. Keep Connections Manageable
- Only accept what you can handle
- Quality over quantity
- Better to decline than underserve

### 5. Use Platform Features
Once connected:
- Create meal plans
- Send payment links
- Track household info
- Maintain professional records

### 6. End Gracefully
When ending connections:
- Complete outstanding orders first
- Communicate clearly
- Offer referrals if appropriate

---

## Troubleshooting

### Can't find a customer's request

**Causes**:
- Request may have expired
- Customer may have cancelled
- Already processed

**Solutions**:
1. Check all sections (Pending, Declined, Ended)
2. Ask customer to resend request
3. Search by name in client list

### Customer says they requested but you don't see it

**Causes**:
- Request not completed on their end
- Email verification pending
- Technical issue

**Solutions**:
1. Ask customer to check their sent requests
2. Verify they completed the request process
3. Have them try again
4. Contact support if persists

### Can't end a connection

**Causes**:
- Outstanding orders pending
- Processing error

**Solutions**:
1. Complete or cancel pending orders first
2. Refresh the page
3. Try again after a few minutes
4. Contact support

### Customer accessing services after decline

**Cause**: Decline may not have processed correctly.

**Solution**:
1. Refresh connections list
2. Verify status shows "Declined"
3. Contact support if access persists

### Connection showing wrong status

**Cause**: Display sync issue.

**Solution**:
1. Refresh the page
2. Log out and back in
3. Clear browser cache

---

## Technical Details

### Data Model

```python
ChefCustomerConnection:
    chef                # FK to Chef
    customer            # FK to Customer
    status              # pending, accepted, declined, ended
    initiated_by        # 'chef' or 'customer'
    created_at          # Request timestamp
    accepted_at         # Acceptance timestamp
    declined_at         # Decline timestamp
    ended_at            # End timestamp
    ended_by            # Who ended (chef/customer)
    notes               # Internal notes
```

### Connection States

```
pending -> accepted -> ended
pending -> declined
pending -> expired (automatic after timeout)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/connections/api/chef/connections/` | GET | List all connections |
| `/connections/api/chef/connections/<id>/accept/` | POST | Accept request |
| `/connections/api/chef/connections/<id>/decline/` | POST | Decline request |
| `/connections/api/chef/connections/<id>/end/` | POST | End connection |
| `/connections/api/customer/request/` | POST | (Customer) Request connection |

### Hooks Integration

The `useConnections` hook provides:
```javascript
const {
  connections,           // All connections
  pendingConnections,    // Pending only
  acceptedConnections,   // Accepted only
  declinedConnections,   // Declined only
  endedConnections,      // Ended only
  respondToConnection,   // Accept/decline/end function
  refetchConnections,    // Refresh data
  isLoading,            // Loading state
  requestError,         // Error state
} = useConnections('chef')
```

### Access Control

| Status | Customer Can | Chef Can |
|--------|-------------|----------|
| **Pending** | Cancel request | Accept/Decline |
| **Accepted** | Book services, Message | Create plans, Send payments |
| **Declined** | View (no action) | View history |
| **Ended** | Request again | Request again |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with two-way connections |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

