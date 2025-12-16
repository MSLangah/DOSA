import streamlit as st
import json
import os
import pandas as pd
import asyncio
import time
from datetime import datetime
from openai import AsyncOpenAI
import shutil
import io
import zipfile
import uuid

# Security configuration
SESSION_TIMEOUT = 18000  # 30 minutes in seconds
HEARTBEAT_INTERVAL = 30  # Send heartbeat every 10 seconds
HEARTBEAT_TIMEOUT = 300  # Consider session dead if no heartbeat for 30 seconds

# ------------------------------
# USER AUTH STORAGE
# ------------------------------
USERS_FILE = "users.json"
ACTIVE_SESSIONS_FILE = "active_sessions.json"

def load_users():
    """Load users"""
    if not os.path.exists(USERS_FILE):
        default_data = {
            "admin": {
                "admin@example.com": "Admin@123"
            },
            "users": {},
            "metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat()
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    """Save users"""
    data["metadata"]["last_modified"] = datetime.now().isoformat()
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_active_sessions():
    """Load all active sessions"""
    if not os.path.exists(ACTIVE_SESSIONS_FILE):
        return {}
    
    try:
        with open(ACTIVE_SESSIONS_FILE, "r") as f:
            sessions = json.load(f)
            
        # Clean expired sessions and sessions without heartbeat
        current_time = time.time()
        active_sessions = {}
        
        for email, session_data in sessions.items():
            # Check session timeout
            if "login_time" in session_data:
                elapsed = current_time - session_data["login_time"]
                if elapsed > SESSION_TIMEOUT:
                    continue  # Skip expired session
            
            # Check heartbeat timeout
            if "last_heartbeat" in session_data:
                heartbeat_elapsed = current_time - session_data["last_heartbeat"]
                if heartbeat_elapsed > HEARTBEAT_TIMEOUT:
                    continue  # Skip dead session (tab closed/browser closed)
            
            active_sessions[email] = session_data
        
        # Save cleaned sessions
        if len(active_sessions) != len(sessions):
            save_active_sessions(active_sessions)
        
        return active_sessions
    except:
        return {}

def save_active_sessions(sessions):
    """Save all active sessions"""
    with open(ACTIVE_SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=4)

def get_user_session(email):
    """Get specific user's session"""
    sessions = load_active_sessions()
    return sessions.get(email)

def set_user_session(email, user_type, session_id):
    """Set user session"""
    sessions = load_active_sessions()
    
    current_time = time.time()
    sessions[email] = {
        "email": email,
        "user_type": user_type,
        "session_id": session_id,
        "login_time": current_time,
        "last_heartbeat": current_time,  # Initialize heartbeat
        "login_timestamp": datetime.now().isoformat()
    }
    
    save_active_sessions(sessions)

def update_heartbeat(email, session_id):
    """Update heartbeat for active session"""
    sessions = load_active_sessions()
    
    if email in sessions and sessions[email].get("session_id") == session_id:
        sessions[email]["last_heartbeat"] = time.time()
        save_active_sessions(sessions)
        return True
    return False

def clear_user_session(email):
    """Clear specific user's session"""
    sessions = load_active_sessions()
    if email in sessions:
        del sessions[email]
        save_active_sessions(sessions)

def verify_user(email, password, session_id):
    """User verification with per-credential session enforcement"""
    data = load_users()
    
    # Check if user credentials are valid
    is_valid = False
    user_type = None
    
    if email in data["admin"]:
        if data["admin"][email] == password:
            is_valid = True
            user_type = "admin"
    elif email in data["users"]:
        if data["users"][email] == password:
            is_valid = True
            user_type = "user"
    
    if not is_valid:
        return False, "Invalid email or password"
    
    # Check if this credential already has an active session
    existing_session = get_user_session(email)
    
    if existing_session:
        # Check if it's the same session (same browser/tab)
        if existing_session.get("session_id") == session_id:
            # Same session trying to authenticate again - allow it
            return True, user_type
        else:
            # Different session with same credentials - block it
            login_time = datetime.fromtimestamp(existing_session["login_time"])
            return False, f"This account is already logged in from another device/tab since {login_time.strftime('%I:%M %p')}. Please logout from that session first."
    
    # No existing session - allow login
    return True, user_type

def is_admin(email):
    """Check if user is admin"""
    data = load_users()
    return email in data["admin"]

# ------------------------------
# SESSION ID MANAGEMENT
# ------------------------------
def get_or_create_session_id():
    """Get or create unique session ID for this browser tab"""
    if "browser_session_id" not in st.session_state:
        st.session_state.browser_session_id = str(uuid.uuid4())
    return st.session_state.browser_session_id

# ------------------------------
# LOGIN SCREEN
# ------------------------------
def login_screen():
    """Login screen"""
    st.title("🔐 Login")
    
    # Get session ID for this browser tab
    session_id = get_or_create_session_id()
    
    # Show active sessions info
    sessions = load_active_sessions()
    active_count = len(sessions)
    
    if active_count > 0:
        st.info(f"ℹ️ Currently {active_count} user(s) logged in from different accounts")
        
        with st.expander("👥 View Active Sessions"):
            for email, session_data in sessions.items():
                login_time = datetime.fromtimestamp(session_data["login_time"])
                elapsed_minutes = int((time.time() - session_data["login_time"]) / 60)
                remaining_minutes = max(0, 30 - elapsed_minutes)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.text(f"📧 {email}")
                with col2:
                    st.text(f"🕐 {login_time.strftime('%I:%M %p')}")
                with col3:
                    st.text(f"⏱️ {remaining_minutes} min left")
                st.divider()
    
    with st.container():
        st.subheader("Access HTML Rewriter Tool")
        
        st.info("ℹ️ **Note:** Each login credential can only be used in one session at a time. Multiple users with different credentials can use the tool simultaneously.")
        
        email = st.text_input("📧 Email Address", key="login_email")
        password = st.text_input("🔑 Password", type="password", key="login_password")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🚀 Login", use_container_width=True):
                if not email or not password:
                    st.error("Please enter both email and password")
                else:
                    success, message = verify_user(email, password, session_id)
                    if success:
                        # Set session for this credential
                        set_user_session(email, message, session_id)
                        
                        # Set session state
                        st.session_state["logged_in"] = True
                        st.session_state["email"] = email
                        st.session_state["user_type"] = message
                        st.session_state["login_time"] = time.time()
                        
                        st.success("✅ Login successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        with col2:
            if st.button("🔄 Clear", use_container_width=True):
                st.rerun()
        
        # Admin force logout section
        st.divider()
        with st.expander("🔧 Admin: Force Logout Any User"):
            st.warning("⚠️ Admin can force logout any active user session")
            admin_email = st.text_input("Admin Email", key="admin_override_email")
            admin_password = st.text_input("Admin Password", type="password", key="admin_override_pass")
            
            if sessions:
                user_to_logout = st.selectbox("Select user to logout", [""] + list(sessions.keys()))
                
                if st.button("Force Logout Selected User", type="primary"):
                    data = load_users()
                    if admin_email in data["admin"] and data["admin"][admin_email] == admin_password:
                        if user_to_logout:
                            clear_user_session(user_to_logout)
                            st.success(f"✅ User '{user_to_logout}' has been logged out!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Please select a user to logout")
                    else:
                        st.error("❌ Invalid admin credentials")
            else:
                st.info("No active sessions to logout")

# ------------------------------
# ENHANCED ADMIN PANEL WITH VIEW USERS
# ------------------------------
def admin_panel():
    """Admin panel for managing users"""
    
    # Add auto-heartbeat component
    auto_heartbeat_component()
    
    st.title("👑 Admin Panel")
    
    if not is_admin(st.session_state["email"]):
        st.error("⚠️ Unauthorized access!")
        return
    
    data = load_users()
    
    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Users", "👥 View Users", "🗑️ Manage Users", "📊 Active Sessions"])
    
    with tab1:
        st.subheader("Add New User")
        
        col1, col2 = st.columns(2)
        with col1:
            new_email = st.text_input("User Email", key="new_user_email")
        with col2:
            new_pass = st.text_input("Password", type="password", key="new_user_pass")
        
        if st.button("Add User", type="primary", key="add_user_btn"):
            if not new_email or not new_pass:
                st.error("Please enter both email and password")
            elif "@" not in new_email or "." not in new_email:
                st.error("Please enter a valid email address")
            elif len(new_pass) < 6:
                st.error("Password must be at least 6 characters")
            else:
                if new_email in data["users"] or new_email in data["admin"]:
                    st.error("User already exists")
                else:
                    data["users"][new_email] = new_pass
                    save_users(data)
                    st.success(f"✅ User '{new_email}' added successfully!")
                    st.info("This user can only access the Tool Page.")
                    time.sleep(1)
                    st.rerun()
    
    with tab2:
        st.subheader("📋 View All Users & Passwords")
        st.info("This section shows all registered users and their passwords.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👑 Admin Users")
            if data["admin"]:
                admin_list = []
                for email, password in data["admin"].items():
                    admin_list.append({
                        "Email": email,
                        "Password": password,
                        "Role": "Admin"
                    })
                
                admin_df = pd.DataFrame(admin_list)
                st.dataframe(admin_df, use_container_width=True, hide_index=True)
                
                csv_admin = admin_df.to_csv(index=False)
                st.download_button(
                    label="📥 Export Admin List",
                    data=csv_admin,
                    file_name="admin_users.csv",
                    mime="text/csv",
                    key="export_admins"
                )
            else:
                st.info("No admin users found")
        
        with col2:
            st.subheader("👤 Regular Users")
            if data["users"]:
                users_list = []
                for email, password in data["users"].items():
                    users_list.append({
                        "Email": email,
                        "Password": password,
                        "Role": "User"
                    })
                
                users_df = pd.DataFrame(users_list)
                st.dataframe(users_df, use_container_width=True, hide_index=True)
                
                csv_users = users_df.to_csv(index=False)
                st.download_button(
                    label="📥 Export User List",
                    data=csv_users,
                    file_name="regular_users.csv",
                    mime="text/csv",
                    key="export_users"
                )
                
                st.metric("Total Regular Users", len(data["users"]))
            else:
                st.info("No regular users found")
        
        st.divider()
        st.subheader("🔍 Search User")
        search_email = st.text_input("Enter email to search", key="search_email")
        
        if search_email:
            found = False
            if search_email in data["admin"]:
                st.success(f"✅ Found Admin User:")
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Email:** {search_email}")
                with col2:
                    st.info(f"**Password:** {data['admin'][search_email]}")
                found = True
            
            if search_email in data["users"]:
                st.success(f"✅ Found Regular User:")
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Email:** {search_email}")
                with col2:
                    st.info(f"**Password:** {data['users'][search_email]}")
                found = True
            
            if not found:
                st.error(f"❌ User '{search_email}' not found")
    
    with tab3:
        st.subheader("Manage Users")
        
        data = load_users()
        
        if "confirm_delete_user" not in st.session_state:
            st.session_state.confirm_delete_user = None
        
        if data["users"]:
            users_list = []
            for email in data["users"].keys():
                users_list.append({
                    "Email": email,
                    "Type": "Regular User"
                })
            
            users_df = pd.DataFrame(users_list)
            st.dataframe(users_df, use_container_width=True, hide_index=True)
            
            st.subheader("🗑️ Remove User")
            user_to_delete = st.selectbox(
                "Select user to remove", 
                [""] + list(data["users"].keys()),
                key="delete_user_select"
            )
            
            if user_to_delete:
                st.info(f"Selected user: **{user_to_delete}**")
                
                if user_to_delete == st.session_state["email"]:
                    st.error("⚠️ Cannot remove your own account!")
                else:
                    if st.session_state.confirm_delete_user != user_to_delete:
                        if st.button("🗑️ Remove This User", type="secondary", key="initial_remove_btn"):
                            st.session_state.confirm_delete_user = user_to_delete
                            st.rerun()
                    else:
                        st.warning(f"⚠️ **Confirm Deletion**")
                        st.error(f"Are you sure you want to permanently delete user **{user_to_delete}**?")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Yes, Delete Permanently", type="primary", key="final_confirm_delete"):
                                current_data = load_users()
                                if user_to_delete in current_data["users"]:
                                    del current_data["users"][user_to_delete]
                                    save_users(current_data)
                                    
                                    # Clear user's active session if exists
                                    clear_user_session(user_to_delete)
                                    
                                    st.success(f"✅ User '{user_to_delete}' has been permanently deleted!")
                                    st.session_state.confirm_delete_user = None
                                    time.sleep(1.5)
                                    st.rerun()
                        
                        with col2:
                            if st.button("❌ Cancel", type="secondary", key="cancel_delete_btn"):
                                st.session_state.confirm_delete_user = None
                                st.rerun()
        else:
            st.info("No users found. Add users using the 'Add Users' tab.")
    
    with tab4:
        st.subheader("📊 Active Session Monitor")
        st.info("View all currently active user sessions. Sessions automatically expire when tab is closed or after 30 seconds of inactivity.")
        
        # Add auto-refresh
        col_refresh1, col_refresh2 = st.columns([3, 1])
        with col_refresh2:
            if st.button("🔄 Refresh Now", use_container_width=True):
                st.rerun()
        
        sessions = load_active_sessions()
        
        if sessions:
            st.success(f"✅ {len(sessions)} active session(s)")
            
            for email, session_data in sessions.items():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    
                    with col1:
                        st.metric("👤 User", email)
                        st.caption(f"Type: {session_data['user_type'].upper()}")
                    
                    with col2:
                        login_time = datetime.fromtimestamp(session_data["login_time"])
                        st.metric("🕐 Login Time", login_time.strftime("%I:%M %p"))
                        
                        # Show heartbeat status
                        last_heartbeat = session_data.get("last_heartbeat", session_data["login_time"])
                        seconds_since = int(time.time() - last_heartbeat)
                        
                        if seconds_since < 15:
                            st.metric("💓 Status", "🟢 Active")
                        elif seconds_since < 30:
                            st.metric("💓 Status", "🟡 Idle")
                        else:
                            st.metric("💓 Status", "🔴 Dead")
                    
                    with col3:
                        elapsed_minutes = int((time.time() - session_data["login_time"]) / 60)
                        remaining_minutes = max(0, 30 - elapsed_minutes)
                        st.metric("⏱️ Time Left", f"{remaining_minutes} min")
                    
                    with col4:
                        if st.button("🚪 Logout", key=f"logout_{email}", use_container_width=True):
                            if st.session_state["email"] == email:
                                st.warning("⚠️ Cannot force logout yourself!")
                            else:
                                clear_user_session(email)
                                st.success(f"✅ Logged out {email}")
                                time.sleep(1)
                                st.rerun()
                    
                    progress = min(1.0, elapsed_minutes / 30)
                    st.progress(progress, text=f"Session: {int(progress * 100)}%")
                    st.divider()
            
            # Auto-refresh notice
            st.caption("💡 Tip: Sessions with no activity for 30 seconds are automatically removed")
        else:
            st.info("ℹ️ No active sessions")
            st.caption("All users are currently logged out")

# ------------------------------
# TOOL PAGE
# ------------------------------
def tool_page():
    """Main tool page"""
    
    # Add auto-heartbeat component at the top
    auto_heartbeat_component()
    
    if check_session_timeout():
        return
    
    st.title("🚀 Bulk Page Generator Rewriter Tool")
    
    user_type = "👑 Admin" if is_admin(st.session_state["email"]) else "👤 User"
    
    # Show session status in a small indicator
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.caption(f"Logged in as: {st.session_state['email']} ({user_type})")
    with col_header2:
        # Show active session indicator
        session = get_user_session(st.session_state["email"])
        if session:
            last_heartbeat = session.get("last_heartbeat", 0)
            seconds_since = int(time.time() - last_heartbeat)
            if seconds_since < 15:
                # Use tooltip with st.success
                st.success("🟢 Active")
                st.caption(f"Last activity: {seconds_since}s ago")  # Added caption for info
            else:
                # Use tooltip with st.warning
                st.warning("🟡 Idle")
                st.caption(f"Last activity: {seconds_since}s ago")  # Added caption for info
                
                    
    if "processing" not in st.session_state:
        st.session_state.processing = False
    
    # File upload sections
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1️⃣ Upload HTML Template")
        html_file = st.file_uploader(
            "Upload template .html", 
            type=["html"], 
            key="html_upload",
            help="Upload your HTML template file"
        )
        
        st.subheader("3️⃣ Enter OpenAI API Key")
        api_key = st.text_input(
            "OpenAI API Key", 
            type="password", 
            key="api_key",
            help="Enter your OpenAI API key"
        )
    
    with col2:
        st.subheader("2️⃣ Upload Keywords")
        
        csv_file = st.file_uploader(
            "Upload CSV or Text file", 
            type=["csv", "txt"], 
            key="csv_upload",
            help="Upload CSV with 'keywords' column or plain text file"
        )
        
        st.subheader("OR Paste Keywords")
        keywords_text = st.text_area(
            "Enter keywords (one per line)",
            height=150,
            help="Enter one keyword per line",
            placeholder="toilet repair and replacement in Austin\nfaucet installation service in Jacksonville FL"
        )
        
        if csv_file or keywords_text:
            st.subheader("📊 Keywords Preview")
            
            keywords_list = get_keywords_list(csv_file, keywords_text)
            
            if keywords_list:
                preview_df = pd.DataFrame(keywords_list[:10], columns=["Keywords"])
                st.dataframe(preview_df, use_container_width=True)
                if len(keywords_list) > 10:
                    st.caption(f"Showing first 10 of {len(keywords_list)} keywords")
            else:
                st.warning("No valid keywords found")

    st.divider()
    
    # Process button
    if st.button("🚀 Start Processing", 
                type="primary", 
                disabled=st.session_state.processing,
                use_container_width=True):
        
        keywords_list = get_keywords_list(csv_file, keywords_text)
        
        if not html_file:
            st.error("⚠️ Please upload HTML template")
            return
        
        if not keywords_list:
            st.error("⚠️ Please provide keywords")
            return
        
        if not api_key:
            st.error("⚠️ Please enter OpenAI API key")
            return
        
        try:
            st.session_state.processing = True
            template_html = html_file.read().decode("utf-8")
            
            st.markdown("---")
            
            st.markdown("""
                <style>
                @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                .processing-container { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin: 20px 0; }
                .processing-title { color: white; font-size: 28px; font-weight: bold; text-align: center; margin-bottom: 20px; animation: pulse 2s ease-in-out infinite; }
                .spinner { border: 8px solid #f3f3f3; border-top: 8px solid #667eea; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin: 20px auto; }
                </style>
            """, unsafe_allow_html=True)
            
            processing_container = st.empty()
            
            with processing_container.container():
                st.markdown('<div class="processing-container">', unsafe_allow_html=True)
                st.markdown('<div class="processing-title">🔄 Processing Your Pages...</div>', unsafe_allow_html=True)
                st.markdown('<div class="spinner"></div>', unsafe_allow_html=True)
                
                progress_bar = st.progress(0, text="Initializing...")
                status_text = st.empty()
                current_keyword = st.empty()
                
                col1, col2, col3 = st.columns(3)
                with col2:
                    success_metric = st.empty()
                with col3:
                    failed_metric = st.empty()
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            results = process_files_with_animation(
                template_html, 
                keywords_list, 
                api_key, 
                progress_bar, 
                status_text,
                current_keyword,
                success_metric,
                failed_metric
            )
            
            processing_container.empty()
            st.balloons()
            
            if results["success_count"] > 0:
                st.success(f"🎉 Successfully generated {results['success_count']} HTML pages!")
                create_download_zip(results["success_count"])
            else:
                st.error("❌ No pages were generated successfully.")
            
            if results["failed_count"] > 0:
                st.warning(f"⚠️ {results['failed_count']} pages failed")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        finally:
            st.session_state.processing = False
    
    if "zip_data" in st.session_state and st.session_state.zip_data:
        show_download_section()

def get_keywords_list(csv_file, keywords_text):
    """Extract keywords from file or text"""
    keywords_list = []
    
    if csv_file:
        try:
            csv_file.seek(0)
            try:
                df = pd.read_csv(csv_file)
                if "keywords" in df.columns:
                    keywords_list = df["keywords"].dropna().astype(str).tolist()
                else:
                    keywords_list = df.iloc[:, 0].dropna().astype(str).tolist()
            except:
                csv_file.seek(0)
                content = csv_file.read().decode('utf-8')
                keywords_list = [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            return []
    
    elif keywords_text:
        keywords_list = [line.strip() for line in keywords_text.split('\n') if line.strip()]
    
    keywords_list = [k for k in keywords_list if k and len(k) > 3]
    return keywords_list

def process_files_with_animation(template_html, keywords_list, api_key, progress_bar, status_text, current_keyword, success_metric, failed_metric):
    """Process files with animated progress"""
    results = {"success_count": 0, "failed_count": 0}
    generated_pages = {}
    
    total_keywords = len(keywords_list)
    MAX_KEYWORDS = 50
    
    if total_keywords > MAX_KEYWORDS:
        st.warning(f"⚠️ Limiting to first {MAX_KEYWORDS} keywords")
        keywords_list = keywords_list[:MAX_KEYWORDS]
        total_keywords = len(keywords_list)
    
    for idx, keyword in enumerate(keywords_list):
        try:
            display_keyword = keyword[:50] + "..." if len(keyword) > 50 else keyword
            current_keyword.markdown(f'📝 Processing: **{display_keyword}**')
            
            client = AsyncOpenAI(api_key=api_key)
            response = asyncio.run(generate_page(client, template_html, keyword, idx))
            
            if response:
                safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_keyword = safe_keyword[:50]
                filename = f"page_{idx+1}_{safe_keyword}.html" if safe_keyword else f"page_{idx+1}.html"
                filename = filename.replace(' ', '_')
                
                generated_pages[filename] = response
                results["success_count"] += 1
                success_metric.metric("Success ✅", results["success_count"])
            else:
                results["failed_count"] += 1
                failed_metric.metric("Failed ❌", results["failed_count"])
                
        except Exception as e:
            results["failed_count"] += 1
            failed_metric.metric("Failed ❌", results["failed_count"])
        
        progress = (idx + 1) / total_keywords
        progress_bar.progress(progress, text=f"⚡ Processing {idx + 1} of {total_keywords}")
        status_text.text(f"✅ Completed: {idx + 1}/{total_keywords} | Success: {results['success_count']} | Failed: {results['failed_count']}")
        time.sleep(0.1)
    
    progress_bar.progress(1.0, text="✅ Complete!")
    st.session_state.generated_pages = generated_pages
    time.sleep(1.5)
    
    return results

def create_download_zip(success_count):
    """Create ZIP file for download"""
    generated_pages = st.session_state.get("generated_pages", {})
    
    if not generated_pages:
        st.error("❌ No pages generated")
        return
    
    try:
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, html_content in generated_pages.items():
                zip_file.writestr(filename, html_content)
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        st.session_state.zip_data = zip_data
        st.session_state.zip_filename = f"html_output_{timestamp}.zip"
        st.session_state.success_count = success_count
        
    except Exception as e:
        st.error(f"❌ Error creating ZIP: {str(e)}")

def show_download_section():
    """Show download section"""
    if "zip_data" not in st.session_state or not st.session_state.zip_data:
        return
    
    st.divider()
    st.subheader("📥 Download Your Files")
    
    st.download_button(
        label=f"📥 Download All {st.session_state.success_count} HTML Files (ZIP)",
        data=st.session_state.zip_data,
        file_name=st.session_state.zip_filename,
        mime="application/zip",
        type="primary",
        use_container_width=True
    )
    
    if st.button("🗑️ Clear Output"):
        for key in ["zip_data", "zip_filename", "generated_pages", "success_count"]:
            if key in st.session_state:
                del st.session_state[key]
        st.success("✅ Cleared!")
        time.sleep(1)
        st.rerun()

async def generate_page(client, html_content, keyword, idx):
    """Generate single page"""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an expert SEO writer. Rewrite the HTML content with the keyword: {keyword}
                Guidelines:
                1. Update headings with location from keyword
                2. Rewrite paragraph text only
                3. Preserve all HTML structure
                4. Output pure HTML only
                5. Make content plagiarism-free"""
                },
                {"role": "user", "content": html_content},
            ],
        )
        return response.choices[0].message.content
    except:
        return None

# ------------------------------
# SESSION MANAGEMENT
# ------------------------------
def check_session_timeout():
    """Check session timeout"""
    if "login_time" not in st.session_state:
        return True
    
    elapsed = time.time() - st.session_state["login_time"]
    if elapsed > SESSION_TIMEOUT:
        st.warning("⏰ Session expired. Please login again.")
        logout_user()
        return True
    
    # Verify session is still valid in active sessions
    session_id = get_or_create_session_id()
    user_session = get_user_session(st.session_state["email"])
    
    if not user_session:
        st.warning("🚪 Your session has expired or been logged out.")
        logout_user()
        return True
    
    if user_session.get("session_id") != session_id:
        st.warning("🔒 Your session has been logged out from another location.")
        logout_user()
        return True
    
    # Update heartbeat to keep session alive
    update_heartbeat(st.session_state["email"], session_id)
    
    return False

def auto_heartbeat_component():
    """Add automatic heartbeat using JavaScript"""
    if "logged_in" in st.session_state and st.session_state.logged_in:
        # JavaScript to detect tab close/visibility and send heartbeat
        st.markdown(f"""
            <script>
            // Heartbeat interval
            let heartbeatInterval = setInterval(function() {{
                // Trigger Streamlit rerun to update heartbeat
                if (document.visibilityState === 'visible') {{
                    // Send a signal that we're still active
                    const rerunEvent = new Event('streamlit:rerun');
                    window.dispatchEvent(rerunEvent);
                }}
            }}, {HEARTBEAT_INTERVAL * 1000});

            // Clear interval when page unloads
            window.addEventListener('beforeunload', function(e) {{
                clearInterval(heartbeatInterval);
            }});

            // Pause heartbeat when tab is hidden, resume when visible
            document.addEventListener('visibilitychange', function() {{
                if (document.hidden) {{
                    clearInterval(heartbeatInterval);
                }} else {{
                    heartbeatInterval = setInterval(function() {{
                        if (document.visibilityState === 'visible') {{
                            const rerunEvent = new Event('streamlit:rerun');
                            window.dispatchEvent(rerunEvent);
                        }}
                    }}, {HEARTBEAT_INTERVAL * 1000});
                }}
            }});
            </script>
        """, unsafe_allow_html=True)

def logout_user():
    """Logout user"""
    # Clear user's active session
    if "email" in st.session_state:
        clear_user_session(st.session_state["email"])
    
    # Clear session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
def show_footer():
    """Display footer with contact information on all pages"""
    st.markdown("---")
    st.markdown("""
        <style>
        .footer {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            margin-top: 30px;
            color: white;
        }
        .footer h3 {
            margin-bottom: 15px;
            color: white;
            font-size: 20px;
        }
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .footer-link {
            color: white;
            text-decoration: none;
            font-size: 16px;
            padding: 8px 15px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .footer-link:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        .footer-copyright {
            margin-top: 15px;
            font-size: 14px;
            opacity: 0.9;
        }
        </style>
        
        <div class="footer">
            <h3>📞 Connect With Us</h3>
            <div class="footer-links">
                <a href="https://wa.me/923059331302" target="_blank" class="footer-link">
                    📱 WhatsApp: +92 305 9331302
                </a>
                <a href="https://www.facebook.com/share/1DWpkagVvy/" target="_blank" class="footer-link">
                    📘 Facebook
                </a>
                <a href="https://www.linkedin.com/in/doctorofseo" target="_blank" class="footer-link">
                    💼 LinkedIn
                </a>
            </div>
            <div class="footer-copyright">
                © 2025 HTML Rewriter Tool | Developed by Dr. Of SEO
            </div>
        </div>
    """, unsafe_allow_html=True)

# ------------------------------
# MAIN APP
# ------------------------------
def main():
    """Main application"""
    
    st.set_page_config(
        page_title="HTML Rewriter Tool - Multi User",
        page_icon="🚀",
        layout="wide"
    )
    
    # Initialize session state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "email" not in st.session_state:
        st.session_state.email = ""
    if "user_type" not in st.session_state:
        st.session_state.user_type = ""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "tool"
    
    # Auto-cleanup dead sessions on every page load
    if st.session_state.logged_in:
        load_active_sessions()  # This will auto-clean dead sessions
    
    # Sidebar
    with st.sidebar:
        if st.session_state.logged_in:
            st.title("🔧 Navigation")
            
            user_type = "👑 Admin" if is_admin(st.session_state["email"]) else "👤 User"
            st.write(f"**User:** {st.session_state['email']}")
            st.write(f"**Role:** {user_type}")
            
            # Show session health indicator
            session = get_user_session(st.session_state["email"])
            if session:
                last_heartbeat = session.get("last_heartbeat", 0)
                seconds_since = int(time.time() - last_heartbeat)
                
                if seconds_since < 15:
                    st.success("🟢 Session Active")
                elif seconds_since < 30:
                    st.warning("🟡 Session Idle")
                else:
                    st.error("🔴 Session Expired")
                
                st.caption(f"Last activity: {seconds_since}s ago")
            
            st.divider()
            
            if is_admin(st.session_state["email"]):
                menu_options = ["🛠️ Tool Page", "👑 Admin Panel", "🚪 Logout"]
                selected = st.radio("Go to:", menu_options, label_visibility="collapsed")
                
                if selected == "🛠️ Tool Page":
                    st.session_state.current_page = "tool"
                elif selected == "👑 Admin Panel":
                    st.session_state.current_page = "admin"
                elif selected == "🚪 Logout":
                    logout_user()
            else:
                menu_options = ["🛠️ Tool Page", "🚪 Logout"]
                selected = st.radio("Go to:", menu_options, label_visibility="collapsed")
                
                if selected == "🛠️ Tool Page":
                    st.session_state.current_page = "tool"
                elif selected == "🚪 Logout":
                    logout_user()
            
            # Show active users count
            st.divider()
            sessions = load_active_sessions()
            active_count = len(sessions)
            st.info(f"👥 {active_count} active user(s)")
    
# Main routing
    if not st.session_state.logged_in:
        login_screen()
        show_footer()  # Show footer on login page
    else:
        if st.session_state.current_page == "admin":
            if is_admin(st.session_state["email"]):
                admin_panel()
                show_footer()  # Show footer on admin page
            else:
                st.error("⚠️ Regular users cannot access Admin Panel")
                st.session_state.current_page = "tool"
                time.sleep(2)
                st.rerun()
        else:
            tool_page()
            show_footer()  # Show footer on tool page

# ------------------------------
# RUN APPLICATION
# ------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        if os.path.exists(USERS_FILE):
            os.remove(USERS_FILE)
        if os.path.exists(ACTIVE_SESSIONS_FILE):
            os.remove(ACTIVE_SESSIONS_FILE)
        print("✅ System reset complete!")
        sys.exit(0)
    
    # Initialize
    load_users()
    
    try:
        main()
    except Exception as e:
        st.error(f"⚠️ Application Error: {str(e)}")
