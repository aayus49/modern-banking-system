import re
import random
import sqlite3
from datetime import datetime
from abc import ABC, abstractmethod
from getpass import getpass
from typing import List, Dict, Optional

# Constants
DB_NAME = "banking.db"
SAVINGS_INTEREST = 0.0945  # 9.45%
CHECKING_FEE = 0.00        # No fees

class Database:
    """Handles all database operations"""
    @staticmethod
    def initialize():
        """Create database tables if they don't exist"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                pin TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Accounts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_number TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                account_type TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
            
            # Transactions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_number) REFERENCES accounts(account_number)
            )
            """)
            conn.commit()

class User:
    """Represents a banking user"""
    def __init__(self, user_id: int, full_name: str, email: str, phone: str, pin: str):
        self.id = user_id
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.pin = pin
    
    @classmethod
    def create(cls, full_name: str, email: str, phone: str, pin: str) -> 'User':
        """Create a new user in database"""
        if not cls._validate_inputs(full_name, email, phone, pin):
            raise ValueError("Invalid user details")
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (full_name, email, phone, pin) VALUES (?, ?, ?, ?)",
                    (full_name, email, phone, pin)
                )
                return cls(cursor.lastrowid, full_name, email, phone, pin)
            except sqlite3.IntegrityError as e:
                raise ValueError("Email or phone already exists")

    @staticmethod
    def _validate_inputs(full_name: str, email: str, phone: str, pin: str) -> bool:
        """Validate user registration inputs"""
        return all([
            re.match(r"^[a-zA-Z ]{2,}$", full_name),
            re.match(r"[^@]+@[^@]+\.[^@]+", email),
            re.match(r"^\d{10}$", phone),
            re.match(r"^\d{4}$", pin)
        ])

    @classmethod
    def authenticate(cls, email: str, pin: str) -> 'User':
        """Authenticate existing user"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, full_name, email, phone, pin FROM users WHERE email = ?",
                (email,)
            )
            user_data = cursor.fetchone()
            
        if not user_data or user_data[4] != pin:
            raise ValueError("Invalid credentials")
        return cls(*user_data)

    def get_accounts(self) -> List[str]:
        """Get all account numbers for this user"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT account_number FROM accounts WHERE user_id = ?",
                (self.id,)
            )
            return [row[0] for row in cursor.fetchall()]

    def generate_account_number(self) -> str:
        """Generate unique account number"""
        prefix = ''.join([c for c in self.full_name[:3] if c.isalpha()]).upper().ljust(3, 'X')
        return f"{prefix}{random.randint(1000, 9999)}"

class BankAccount(ABC):
    """Abstract base class for bank accounts"""
    def __init__(self, account_number: str, user: User, balance: float = 0.0):
        self.account_number = account_number
        self.user = user
        self.balance = balance
    
    @classmethod
    def get_account(cls, account_number: str) -> 'BankAccount':
        """Retrieve account from database"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT a.account_number, a.user_id, a.balance, a.account_type,
                      u.full_name, u.email, u.phone
                   FROM accounts a
                   JOIN users u ON a.user_id = u.id
                   WHERE a.account_number = ?""",
                (account_number,)
            )
            account_data = cursor.fetchone()
            
        if not account_data:
            raise ValueError("Account not found")
            
        user = User(account_data[1], account_data[4], account_data[5], account_data[6], "")
        
        if account_data[3] == "savings":
            return SavingsAccount(account_data[0], user, account_data[2])
        elif account_data[3] == "checking":
            return CheckingAccount(account_data[0], user, account_data[2])
        raise ValueError("Invalid account type")

    def deposit(self, amount: float) -> bool:
        """Deposit money into account"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE accounts SET balance = balance + ? WHERE account_number = ?",
                    (amount, self.account_number)
                )
                cursor.execute(
                    """INSERT INTO transactions 
                       (account_number, amount, transaction_type)
                       VALUES (?, ?, ?)""",
                    (self.account_number, amount, "deposit")
                )
                conn.commit()
                self.balance += amount
                return True
            except Exception as e:
                conn.rollback()
                raise ValueError(f"Deposit failed: {str(e)}")

    def withdraw(self, amount: float) -> bool:
        """Withdraw money from account"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE accounts SET balance = balance - ? WHERE account_number = ?",
                    (amount, self.account_number)
                )
                cursor.execute(
                    """INSERT INTO transactions 
                       (account_number, amount, transaction_type)
                       VALUES (?, ?, ?)""",
                    (self.account_number, amount, "withdrawal")
                )
                conn.commit()
                self.balance -= amount
                return True
            except Exception as e:
                conn.rollback()
                raise ValueError(f"Withdrawal failed: {str(e)}")

    def get_transactions(self, limit: int = 10) -> List[Dict]:
        """Get transaction history"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT amount, transaction_type, timestamp
                   FROM transactions
                   WHERE account_number = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (self.account_number, limit)
            )
            return [
                {
                    "amount": row[0],
                    "type": row[1],
                    "timestamp": datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
                }
                for row in cursor.fetchall()
            ]

    @abstractmethod
    def get_account_type(self) -> str:
        """Return account type"""
        pass

    @abstractmethod
    def apply_monthly_update(self) -> bool:
        """Apply monthly updates"""
        pass

    def __str__(self) -> str:
        return (f"Account Number: {self.account_number}\n"
                f"Account Holder: {self.user.full_name}\n"
                f"Balance: £{self.balance:.2f}\n"
                f"Type: {self.get_account_type()}")

class SavingsAccount(BankAccount):
    """Savings account with interest"""
    def __init__(self, account_number: str, user: User, balance: float = 0.0):
        super().__init__(account_number, user, balance)
        self.interest_rate = SAVINGS_INTEREST

    def get_account_type(self) -> str:
        return "Savings Account"

    def apply_monthly_update(self) -> bool:
        """Apply monthly interest"""
        interest = self.balance * (self.interest_rate / 12)
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE accounts SET balance = balance + ? WHERE account_number = ?",
                    (interest, self.account_number)
                )
                cursor.execute(
                    """INSERT INTO transactions 
                       (account_number, amount, transaction_type)
                       VALUES (?, ?, ?)""",
                    (self.account_number, interest, "interest")
                )
                conn.commit()
                self.balance += interest
                return True
            except Exception as e:
                conn.rollback()
                raise ValueError(f"Monthly update failed: {str(e)}")

class CheckingAccount(BankAccount):
    """Checking account with no fees"""
    def get_account_type(self) -> str:
        return "Checking Account"

    def apply_monthly_update(self) -> bool:
        """No monthly updates for checking accounts"""
        return True

class Bank:
    """Core banking system"""
    @staticmethod
    def create_account(user: User, account_type: str) -> BankAccount:
        """Create new bank account"""
        account_number = user.generate_account_number()
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO accounts (account_number, user_id, account_type) VALUES (?, ?, ?)",
                    (account_number, user.id, account_type.lower())
                )
                
                if account_type.lower() == "savings":
                    account = SavingsAccount(account_number, user)
                elif account_type.lower() == "checking":
                    account = CheckingAccount(account_number, user)
                else:
                    raise ValueError("Invalid account type")
                    
                conn.commit()
                return account
            except Exception as e:
                conn.rollback()
                raise ValueError(f"Account creation failed: {str(e)}")

class BankCLI:
    """Command Line Interface for banking system"""
    def __init__(self):
        Database.initialize()
        self.current_user: Optional[User] = None
        self.current_account: Optional[BankAccount] = None

    def run(self):
        """Main application loop"""
        print("\n=== Modern Banking System ===")
        while True:
            try:
                if not self.current_user:
                    self._show_auth_menu()
                elif not self.current_account:
                    self._show_user_menu()
                else:
                    self._show_account_menu()
            except KeyboardInterrupt:
                print("\nThank you for banking with us!")
                break
            except Exception as e:
                print(f"\nError: {e}")

    def _show_auth_menu(self):
        """Authentication menu"""
        print("\n1. Register")
        print("2. Login")
        print("3. Exit")
        
        choice = input("Select option: ")
        if choice == "1":
            self._register_user()
        elif choice == "2":
            self._login_user()
        elif choice == "3":
            exit()
        else:
            print("Invalid option")

    def _register_user(self):
        """Handle user registration"""
        print("\n--- Registration ---")
        full_name = input("Full name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone (10 digits): ").strip()
        pin = getpass("Set 4-digit PIN: ").strip()
        
        try:
            self.current_user = User.create(full_name, email, phone, pin)
            print(f"\nWelcome {self.current_user.full_name}! Registration successful.")
        except ValueError as e:
            print(f"\nRegistration failed: {e}")

    def _login_user(self):
        """Handle user login"""
        print("\n--- Login ---")
        email = input("Email: ").strip()
        pin = getpass("PIN: ").strip()
        
        try:
            self.current_user = User.authenticate(email, pin)
            print(f"\nWelcome back, {self.current_user.full_name}!")
        except ValueError as e:
            print(f"\nLogin failed: {e}")

    def _show_user_menu(self):
        """Main user menu"""
        print(f"\n--- Welcome, {self.current_user.full_name} ---")
        print("1. Create Account")
        print("2. Select Account")
        print("3. Logout")
        
        choice = input("Select option: ")
        if choice == "1":
            self._create_account()
        elif choice == "2":
            self._select_account()
        elif choice == "3":
            self.current_user = None
            print("Logged out successfully")
        else:
            print("Invalid option")

    def _create_account(self):
        """Handle account creation"""
        print("\n--- Create Account ---")
        print("Account types: Savings | Checking")
        acc_type = input("Enter account type: ").strip().lower()
        
        try:
            self.current_account = Bank.create_account(self.current_user, acc_type)
            print(f"\nAccount created successfully!\n{self.current_account}")
            self.current_account = None  # Return to account selection
        except ValueError as e:
            print(f"\nError: {e}")

    def _select_account(self):
        """Handle account selection"""
        accounts = self.current_user.get_accounts()
        if not accounts:
            print("\nNo accounts found. Please create an account first.")
            return
            
        print("\nYour Accounts:")
        for i, acc_num in enumerate(accounts, 1):
            # Get account type for display
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT account_type FROM accounts WHERE account_number = ?",
                    (acc_num,)
                )
                acc_type = cursor.fetchone()[0]
            print(f"{i}. {acc_num} ({acc_type.capitalize()})")
            
        try:
            choice = int(input("Select account: ")) - 1
            if 0 <= choice < len(accounts):
                self.current_account = BankAccount.get_account(accounts[choice])
                print(f"\nSelected {self.current_account.get_account_type()}")
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a valid number")

    def _show_account_menu(self):
        """Account operations menu"""
        print(f"\n--- {self.current_account.get_account_type()} ---")
        print(f"Account: {self.current_account.account_number}")
        print(f"Balance: £{self.current_account.balance:.2f}")
        print("\n1. Deposit")
        print("2. Withdraw")
        print("3. View Transactions")
        print("4. Back to Accounts")
        
        choice = input("Select option: ")
        if choice == "1":
            self._handle_deposit()
        elif choice == "2":
            self._handle_withdrawal()
        elif choice == "3":
            self._view_transactions()
        elif choice == "4":
            self.current_account = None
        else:
            print("Invalid option")

    def _handle_deposit(self):
        """Handle deposit operation"""
        try:
            amount = float(input("Enter deposit amount: "))
            if self.current_account.deposit(amount):
                print(f"\nDeposit successful. New balance: £{self.current_account.balance:.2f}")
        except ValueError as e:
            print(f"\nError: {e}")

    def _handle_withdrawal(self):
        """Handle withdrawal operation"""
        try:
            amount = float(input("Enter withdrawal amount: "))
            if self.current_account.withdraw(amount):
                print(f"\nWithdrawal successful. New balance: £{self.current_account.balance:.2f}")
        except ValueError as e:
            print(f"\nError: {e}")

    def _view_transactions(self):
        """Display transaction history"""
        transactions = self.current_account.get_transactions()
        if not transactions:
            print("\nNo transactions found")
            return
            
        print("\nRecent Transactions:")
        for t in transactions:
            print(f"{t['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - {t['type'].capitalize()}: £{t['amount']:.2f}")

if __name__ == "__main__":
    try:
        BankCLI().run()
    except Exception as e:
        print(f"Application error: {e}")