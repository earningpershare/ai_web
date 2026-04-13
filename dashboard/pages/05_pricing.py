"""
方案與訂閱 — 三方案定價頁面 + 綠界付款
"""
import os

import streamlit as st
import requests as _requests

from auth import auth_sidebar, is_logged_in, has_plan, show_login_modal, current_plan, PLAN_LABEL

