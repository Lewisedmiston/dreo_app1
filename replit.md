# Overview

Dreo Kitchen Ops App is a chef-friendly MVP Streamlit application designed to replace Excel-based costing workflows for restaurant operations. The app provides a comprehensive food cost management system that handles vendor catalog uploads, ingredient master management, recipe costing, and menu analysis. It focuses on streamlining the process of tracking food costs, managing vendor relationships, and calculating accurate plate costs to maintain target food cost percentages.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: Streamlit web application with multi-page navigation
- **Page Structure**: Modular page-based design with each major function as a separate page
- **User Interface**: Simple, form-based interface optimized for restaurant staff workflow
- **Navigation**: Sidebar navigation between different modules (Upload, Ingredients, Recipes, etc.)

## Backend Architecture
- **Database**: SQLite with SQLAlchemy integration for data persistence
- **Data Processing**: Pandas for data manipulation and Excel file handling
- **Costing Engine**: Custom costing module with unit conversion capabilities
- **ETL Pipeline**: Specialized ETL module for processing vendor catalog uploads with pack/size parsing

## Data Storage Solutions
- **Primary Database**: SQLite (dreo.db) for all operational data
- **Schema Design**: Normalized relational schema with vendors, catalog_items, ingredients, recipes, and recipe_lines tables
- **Audit Trail**: Exception tracking and changelog tables for data quality and change management
- **File Handling**: Support for CSV and Excel file uploads with automatic format detection

## Core Business Logic
- **Unit Conversion System**: Comprehensive conversion between different units of measure (oz, lb, g, kg, ml, L, etc.)
- **Cost Calculation**: Dual costing approach supporting both per-ounce and per-each pricing
- **Recipe Costing**: Hierarchical recipe structure supporting ingredients and sub-recipes
- **Food Cost Analysis**: Real-time calculation of food cost percentages against configurable targets

## Configuration Management
- **Environment Variables**: Configurable food cost target percentage and database path
- **Vendor Management**: Predefined vendor list with extensibility for new vendors
- **Settings Module**: Centralized configuration with environment variable support

# External Dependencies

## Python Libraries
- **Streamlit**: Web application framework for the user interface
- **Pandas**: Data manipulation and analysis for catalog processing and reporting
- **SQLAlchemy**: Database ORM and connection management
- **psycopg2-binary**: PostgreSQL adapter (prepared for potential database migration)
- **openpyxl/XlsxWriter**: Excel file reading and writing capabilities
- **python-dotenv**: Environment variable management
- **requests**: HTTP client for potential API integrations

## Development Tools
- **VS Code Configuration**: Integrated development environment setup with Python debugging
- **DevContainer Support**: Containerized development environment with Python 3.11
- **Task Automation**: VS Code tasks for running, formatting, and linting

## Data Sources
- **Vendor Catalogs**: CSV and Excel file uploads from food service distributors (auto-detected vendors based on what you upload)
- **Manual Data Entry**: Recipe creation and ingredient management through web interface
- **Configuration Files**: Environment-based settings for operational parameters

## Export Capabilities
- **Excel Workbook Generation**: Multi-sheet Excel export with formatted reports
- **Data Download**: Streamlit-based file download functionality for generated reports