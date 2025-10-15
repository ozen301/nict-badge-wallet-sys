# AGENTS.md

## Overview
The **NICT Project** (Tohoku University, Japan) pilots a blockchain-based reward system to stimulate local economies.  
During the November 2025 basketball series, users earn NFT badges for attending games and visiting partner restaurants.  
Badges enable **bingo gameplay** and a **prize draw** mechanism.

---

## System Architecture
| Component                                   | Function                                                             |
| ------------------------------------------- | -------------------------------------------------------------------- |
| **API Gateway**                             | Handles routing, authentication, and rate limiting.                  |
| **Badge & Wallet System (This Repository)** | SQLAlchemy backend managing users, wallets, badges, and prize draws. |
| **Badge App**                               | Mobile/web interface for displaying badges and rewards.              |
| **Blockchain (YenPoint)**                   | External service minting NFTs on Bitcoin SV.                         |

**Flow:**  
User → App → API → Badge & Wallet → Blockchain  

---

## NFT & Gameplay Flow
1. Users receive NFT badges via the app.  
2. Badges of specific types initiate a **3×3 bingo** (1 game badge + 8 restaurant/event goals).  
3. Completing a line grants rewards.

---

## Prize-Draw System

### Purpose
Each NFT deterministically produces a **draw number** from its `origin`.  
This value is compared with a **winning number** to determine outcomes — instant or event-based.

### Data Model
- **PrizeDrawType** – defines algorithm and thresholds.  
- **PrizeDrawWinningNumber** – stores winning numbers.  
- **PrizeDrawResult** – links NFT, user, and draw outcome.

---
