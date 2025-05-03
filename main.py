"""
Banking System Application
==========================
This application demonstrates Object-Oriented Programming principles:
1. Encapsulation - Protecting data through private attributes and getters/setters
2. Inheritance - Base BankAccount class with specialized account types
3. Polymorphism - Different implementations of methods in child classes
4. Abstraction - Abstract base class with required method implementations
5. Composition - User contains accounts, accounts contain transactions

The system uses SQLite for persistent storage of users, accounts, and transactions.
"""

import re
import random
import sqlite3
from datetime import datetime
from abc import ABC, abstractmethod
from getpass import getpass
from typing import List, Dict, Optional

# Database configuration
DB_NAME = "banking_system.db"

# Constants for account parameters
SAVINGS_INTEREST_RATE = 0.0945  # 9.45% per annum fixed interest rate
CHECKING_TRANSACTION_FEE = 0.00  # No fees for checking accounts
MAX_WITHDRAWAL_LIMIT = 1000.00  # Maximum withdrawal amount per transaction

def initialize_database():
    """
    Initialize the SQLite database with required tables.
    Demonstrates database schema design for a banking system.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table stores customer information
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
    
    # Accounts table stores account information
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        account_number TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Transactions table records all financial transactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_number TEXT NOT NULL,
        amount REAL NOT NULL,
        transaction_type TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (account_number) REFERENCES accounts (account_number)
    )
    """)
    
    conn.commit()
    conn.close()

class Transaction:
    """
    Represents a financial transaction.
    Demonstrates encapsulation with validated attributes.
    """
    def __init__(self, amount: float, transaction_type: str, timestamp=None):
        # Validation ensures data integrity (Encapsulation)
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Amount must be positive number")
        if transaction_type not in ['deposit', 'withdrawal', 'fee', 'interest']:
            raise ValueError("Invalid transaction type")
            
        self.amount = amount
        self.type = transaction_type
        self.timestamp = timestamp if timestamp else datetime.now()

    def __str__(self):
        """String representation of transaction (Polymorphism)"""
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {self.type.capitalize()}: £{self.amount:.2f}"

class User:
    """
    Represents a banking user.
    Demonstrates encapsulation and database persistence.
    """
    def __init__(self, user_id: int, full_name: str, email: str, phone: str, pin: str):
        # All attributes are protected (Encapsulation)
        self.id = user_id
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.pin = pin

    @classmethod
    def create(cls, full_name: str, email: str, phone: str, pin: str):
        """
        Creates a new user with validation.
        Demonstrates data validation and database operations.
        """
        if not cls._validate_inputs(full_name, email, phone, pin):
            raise ValueError("Invalid user details")
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (full_name, email, phone, pin) VALUES (?, ?, ?, ?)",
                (full_name, email, phone, pin)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return cls(user_id, full_name, email, phone, pin)
        except sqlite3.IntegrityError as e:
            if "email" in str(e):
                raise ValueError("Email already registered")
            elif "phone" in str(e):
                raise ValueError("Phone number already registered")
            raise
        finally:
            conn.close()

    @staticmethod
    def _validate_inputs(full_name: str, email: str, phone: str, pin: str) -> bool:
        """
        Validates user input using regular expressions.
        Demonstrates input validation.
        """
        return all([
            re.match(r"^[a-zA-Z ]{2,}$", full_name),
            re.match(r"[^@]+@[^@]+\.[^@]+", email),
            re.match(r"^\d{10}$", phone),
            re.match(r"^\d{4}$", pin)
        ])

    @classmethod
    def authenticate(cls, email: str, pin: str):
        """
        Authenticates user credentials.
        Demonstrates database query and validation.
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, full_name, email, phone, pin FROM users WHERE email = ?",
            (email,)
        )
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data or user_data[4] != pin:
            raise ValueError("Invalid credentials")
        return cls(*user_data)

    def get_accounts(self) -> List[str]:
        """
        Retrieves all accounts for this user.
        Demonstrates database relationship query.
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT account_number FROM accounts WHERE user_id = ?",
            (self.id,)
        )
        accounts = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return accounts

    def generate_account_number(self) -> str:
        """
        Generates unique account number from user's name.
        Demonstrates business logic implementation.
        """
        prefix = ''.join([c for c in self.full_name[:3] if c.isalpha()]).upper().ljust(3, 'X')
        return f"{prefix}{random.randint(1000, 9999)}"

class BankAccount(ABC):
    """
    Abstract base class for bank accounts.
    Demonstrates abstraction and inheritance.
    """
    def __init__(self, account_number: str, user: User, balance: float = 0.0):
        # Protected attributes (Encapsulation)
        self._account_number = account_number
        self._user = user
        self._balance = balance
        self._transactions = []

    def check_balance(self) -> float:
        """
        Returns the current account balance.
        Demonstrates simple getter method (Encapsulation).
        """
        return self._balance

    @classmethod
    def get_account(cls, account_number: str):
        """
        Retrieves account from database.
        Demonstrates polymorphism through factory method.
        """
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # For dictionary-style access
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
        conn.close()
        
        if not account_data:
            raise ValueError("Account not found")
            
        user = User(account_data["user_id"], account_data["full_name"], 
                   account_data["email"], account_data["phone"], "")
        
        # Polymorphism - return appropriate account type
        if account_data["account_type"] == "savings":
            return SavingsAccount(account_data["account_number"], user, account_data["balance"])
        elif account_data["account_type"] == "checking":
            return CheckingAccount(account_data["account_number"], user, account_data["balance"])
        raise ValueError("Unknown account type")

    def deposit(self, amount: float) -> bool:
        """
        Deposits money into account.
        Demonstrates database transaction handling.
        """
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Amount must be positive number")
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Update balance
            cursor.execute(
                "UPDATE accounts SET balance = balance + ? WHERE account_number = ?",
                (amount, self._account_number)
            )
            
            # Record transaction
            cursor.execute(
                """INSERT INTO transactions 
                   (account_number, amount, transaction_type) 
                   VALUES (?, ?, ?)""",
                (self._account_number, amount, "deposit")
            )
            
            conn.commit()
            self._balance += amount
            self._transactions.append(Transaction(amount, "deposit"))
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Deposit failed: {str(e)}")
        finally:
            conn.close()

    def withdraw(self, amount: float) -> bool:
        """
        Withdraws money from account with £1000 limit per transaction.
        Demonstrates transaction handling with error recovery.
        """
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Amount must be positive number")
        if amount > MAX_WITHDRAWAL_LIMIT:
            raise ValueError(f"Withdrawal limit exceeded. Maximum per transaction: £{MAX_WITHDRAWAL_LIMIT:.2f}")
        if amount > self._balance:
            raise ValueError("Insufficient funds")
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Update balance
            cursor.execute(
                "UPDATE accounts SET balance = balance - ? WHERE account_number = ?",
                (amount, self._account_number)
            )
            
            # Record transaction
            cursor.execute(
                """INSERT INTO transactions 
                   (account_number, amount, transaction_type) 
                   VALUES (?, ?, ?)""",
                (self._account_number, amount, "withdrawal")
            )
            
            conn.commit()
            self._balance -= amount
            self._transactions.append(Transaction(amount, "withdrawal"))
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Withdrawal failed: {str(e)}")
        finally:
            conn.close()

    def get_transactions(self, limit=20) -> List[Dict]:
        """
        Retrieves transaction history.
        Demonstrates database query and result formatting.
        """
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # For dictionary-style access
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT amount, transaction_type as type, timestamp 
               FROM transactions 
               WHERE account_number = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (self._account_number, limit)
        )
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                "amount": row["amount"],
                "type": row["type"],
                "timestamp": datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S") 
                    if isinstance(row["timestamp"], str) 
                    else row["timestamp"]
            })
        
        conn.close()
        return transactions

    @abstractmethod
    def get_account_type(self) -> str:
        """Abstract method to be implemented by subclasses (Abstraction)"""
        pass

    @abstractmethod
    def apply_monthly_update(self) -> bool:
        """Abstract method for monthly updates (Abstraction)"""
        pass

    def __str__(self) -> str:
        """String representation of account (Polymorphism)"""
        return (f"Account: {self._account_number}\n"
                f"Holder: {self._user.full_name}\n"
                f"Balance: £{self._balance:.2f}\n"
                f"Type: {self.get_account_type()}")

class SavingsAccount(BankAccount):
    """
    Savings account implementation.
    Demonstrates inheritance and method overriding.
    """
    def __init__(self, account_number: str, user: User, balance: float = 0.0):
        super().__init__(account_number, user, balance)
        self._interest_rate = SAVINGS_INTEREST_RATE

    def get_account_type(self) -> str:
        """Returns account type (Polymorphism)"""
        return "Savings Account (9.45% interest)"

    def apply_monthly_update(self) -> bool:
        """
        Applies monthly interest.
        Demonstrates business logic implementation.
        """
        interest = self._balance * (self._interest_rate / 12)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Update balance
            cursor.execute(
                "UPDATE accounts SET balance = balance + ? WHERE account_number = ?",
                (interest, self._account_number)
            )
            
            # Record transaction
            cursor.execute(
                """INSERT INTO transactions 
                   (account_number, amount, transaction_type) 
                   VALUES (?, ?, ?)""",
                (self._account_number, interest, "interest")
            )
            
            conn.commit()
            self._balance += interest
            self._transactions.append(Transaction(interest, "interest"))
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Monthly update failed: {str(e)}")
        finally:
            conn.close()

class CheckingAccount(BankAccount):
    """
    Checking account implementation.
    Demonstrates inheritance and method overriding.
    """
    def get_account_type(self) -> str:
        """Returns account type (Polymorphism)"""
        return "Checking Account (no fees)"

    def apply_monthly_update(self) -> bool:
        """Checking accounts have no monthly updates"""
        return True

class Bank:
    """
    Core banking system operations.
    Demonstrates separation of concerns.
    """
    @staticmethod
    def create_account(user: User, account_type: str) -> BankAccount:
        """
        Creates a new bank account.
        Demonstrates factory pattern.
        """
        account_number = user.generate_account_number()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO accounts (account_number, user_id, account_type) VALUES (?, ?, ?)",
                (account_number, user.id, account_type.lower())
            )
            
            # Polymorphism - create appropriate account type
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
        finally:
            conn.close()

    @staticmethod
    def get_account_type(account_number: str) -> str:
        """
        Retrieves account type for display.
        Demonstrates utility method.
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT account_type FROM accounts WHERE account_number = ?",
            (account_number,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            raise ValueError("Account not found")
        return result[0]

class BankCLI:
    """
    Command Line Interface for banking system.
    Demonstrates user interaction handling.
    """
    def __init__(self):
        initialize_database()
        self._current_user: Optional[User] = None
        self._current_account: Optional[BankAccount] = None

    def run(self):
        """Main application loop"""
        print("\n=== Modern Banking System ===")
        while True:
            try:
                if not self._current_user:
                    self._show_auth_menu()
                elif not self._current_account:
                    self._show_user_menu()
                else:
                    self._show_account_menu()
            except KeyboardInterrupt:
                print("\nThank you for banking with us!")
                break
            except Exception as e:
                print(f"\nError: {e}")

    def _show_auth_menu(self):
        """Displays authentication menu"""
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
        """Handles user registration"""
        print("\n--- Registration ---")
        full_name = input("Full name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone (10 digits): ").strip()
        pin = getpass("Set 4-digit PIN: ").strip()
        
        try:
            self._current_user = User.create(full_name, email, phone, pin)
            print(f"\nWelcome {self._current_user.full_name}! Registration successful.")
        except ValueError as e:
            print(f"\nRegistration failed: {e}")

    def _login_user(self):
        """Handles user login"""
        print("\n--- Login ---")
        email = input("Email: ").strip()
        pin = getpass("PIN: ").strip()
        
        try:
            self._current_user = User.authenticate(email, pin)
            print(f"\nWelcome back, {self._current_user.full_name}!")
        except ValueError as e:
            print(f"\nLogin failed: {e}")

    def _show_user_menu(self):
        """Displays main user menu"""
        print(f"\n--- Welcome, {self._current_user.full_name} ---")
        print("1. Create Account")
        print("2. Select Account")
        print("3. Logout")
        
        choice = input("Select option: ")
        if choice == "1":
            self._create_account()
        elif choice == "2":
            self._select_account()
        elif choice == "3":
            self._current_user = None
            print("Logged out successfully")
        else:
            print("Invalid option")

    def _create_account(self):
        """Handles account creation"""
        print("\n--- Create Account ---")
        print("Account types: Savings | Checking")
        acc_type = input("Enter account type: ").strip().lower()
        
        try:
            self._current_account = Bank.create_account(self._current_user, acc_type)
            print(f"\nAccount created successfully!\n{self._current_account}")
            self._current_account = None  # Return to account selection
        except ValueError as e:
            print(f"\nError: {e}")

    def _select_account(self):
        """Handles account selection with type display"""
        accounts = self._current_user.get_accounts()
        if not accounts:
            print("\nNo accounts found. Please create an account first.")
            return
            
        print("\nYour Accounts:")
        for i, acc_num in enumerate(accounts, 1):
            acc_type = Bank.get_account_type(acc_num)
            print(f"{i}. {acc_num} ({acc_type.capitalize()})")
            
        try:
            choice = int(input("Select account: ")) - 1
            if 0 <= choice < len(accounts):
                self._current_account = BankAccount.get_account(accounts[choice])
                print(f"\nSelected {self._current_account.get_account_type()}")
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a valid number")

    def _show_account_menu(self):
        """Displays account operations menu"""
        print(f"\n--- {self._current_account.get_account_type()} ---")
        print(f"Account: {self._current_account._account_number}")
        print(f"Balance: £{self._current_account.check_balance():.2f}")
        print(f"Withdrawal Limit: £{MAX_WITHDRAWAL_LIMIT:.2f} per transaction")
        print("\n1. Deposit")
        print("2. Withdraw")
        print("3. Check Balance")
        print("4. View Transactions")
        print("5. Back to Accounts")
        
        choice = input("Select option: ")
        if choice == "1":
            self._handle_deposit()
        elif choice == "2":
            self._handle_withdrawal()
        elif choice == "3":
            self._check_balance()
        elif choice == "4":
            self._view_transactions()
        elif choice == "5":
            self._current_account = None
        else:
            print("Invalid option")

    def _handle_deposit(self):
        """Handles deposit operation"""
        try:
            amount = float(input("Enter deposit amount: "))
            if self._current_account.deposit(amount):
                print(f"\nDeposit successful. New balance: £{self._current_account.check_balance():.2f}")
        except ValueError as e:
            print(f"\nError: {e}")

    def _handle_withdrawal(self):
        """Handles withdrawal operation with limit check"""
        try:
            amount = float(input(f"Enter withdrawal amount (Max £{MAX_WITHDRAWAL_LIMIT:.2f}): "))
            if self._current_account.withdraw(amount):
                print(f"\nWithdrawal successful. New balance: £{self._current_account.check_balance():.2f}")
        except ValueError as e:
            print(f"\nError: {e}")

    def _check_balance(self):
        """Displays current account balance"""
        balance = self._current_account.check_balance()
        print(f"\nCurrent Balance: £{balance:.2f}")
        print(f"Withdrawal Limit: £{MAX_WITHDRAWAL_LIMIT:.2f} per transaction")

    def _view_transactions(self):
        """
        Displays transaction history in formatted table.
        Demonstrates output formatting and data presentation.
        """
        try:
            transactions = self._current_account.get_transactions()
            if not transactions:
                print("\nNo transactions found for this account.")
                return
                
            print(f"\nTransaction History for {self._current_account._account_number}")
            print("-" * 50)
            print(f"{'Date/Time':<20} | {'Type':<12} | {'Amount':>12}")
            print("-" * 50)
            
            for t in transactions:
                timestamp = t["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
                print(f"{timestamp:<20} | "
                      f"{t['type'].capitalize():<12} | "
                      f"£{t['amount']:>10.2f}")
            
            print("-" * 50)
            print(f"Current Balance: £{self._current_account.check_balance():.2f}")
            
        except Exception as e:
            print(f"\nError viewing transactions: {e}")

if __name__ == "__main__":
    try:
        BankCLI().run()
    except Exception as e:
        print(f"Application error: {e}")