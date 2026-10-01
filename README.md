# Multi-Tenant Modular SaaS Platform

A Django-based multi-tenant SaaS platform designed to support multiple types of businesses through a modular architecture.

The project is being developed as a portfolio project to explore real-world Django application architecture, multi-tenancy, business logic, authorization, and reusable modules.

> **Project Status:** In active development

---

## Overview

The goal of this project is to build a single SaaS platform that can support different business types without creating a separate application for each business.

The platform uses a **workspace-based multi-tenant architecture**, where each business operates within its own workspace and business data is isolated at the database query level.

The planned platform consists of approximately **7 reusable modules** that can be combined to support around **9 different types of businesses**.

---

## Key Features

* Workspace-based multi-tenancy
* Row-level tenant data isolation
* Middleware-based workspace context
* Reusable tenant-aware base model
* Custom Django QuerySets and Managers
* Soft-delete infrastructure
* Modular application architecture
* Service-layer business logic
* Selector-based data retrieval
* Workspace-aware validation
* Role and permission-based authorization
* Reusable business modules

---

## Architecture

The project follows a separation of responsibilities between models, selectors, services, and validation logic.

```text
Request
   │
   ▼
Middleware
   │
   └── Determine current workspace
            │
            ▼
      Workspace Context
            │
      ┌─────┴─────┐
      ▼           ▼
  Selectors    Services
      │           │
      └─────┬─────┘
            ▼
     Tenant-aware Models
            │
            ▼
         Database
```

The goal is to keep business rules out of views and make domain operations easier to maintain and test.

---

## Multi-Tenancy

Each business operates inside a `Workspace`.

The application establishes the current workspace during the request lifecycle and makes it available to tenant-aware application components.

Business models inherit from a reusable base model that provides workspace awareness and soft-delete functionality.

Custom QuerySets and Managers are used to ensure that normal queries are automatically scoped to the current workspace.

Conceptually:

```text
User
 │
 └── Workspace Membership
          │
          ▼
       Workspace
          │
          ▼
     Business Data
```

This allows multiple businesses to use the same application while keeping their data logically isolated.

---

## Modules

The platform is being designed around reusable modules rather than a single business-specific application.

Current development includes:

### Inventory

The Inventory module is the most developed module so far.

It includes functionality and domain models for areas such as:

* Products
* Product variants
* Warehouses
* Stock
* Suppliers
* Stock allocation and release
* Stock adjustments
* Stock transfers
* Inventory tracking
* Inventory-related business rules

The module uses selectors for data retrieval and services for domain operations and business logic.

### CRM

The CRM module is currently under development.

Planned areas include:

* Customers
* Leads
* Pipelines
* Deals
* Customer-related business workflows

Additional modules are planned as the project develops.

---

## Technology Stack

* **Python**
* **Django**
* **Django ORM**
* **Git**
* **GitHub**
* HTML / CSS for basic web interfaces

Additional technologies may be introduced as the project develops.

---

## Project Structure

The application is organized around business domains and shared platform functionality.

A simplified structure is:

```text
project/
│
├── authorization/
├── identity/
├── tenancy/
│
├── inventory/
│   ├── catalogue/
│   ├── locations/
│   ├── stock/
│   └── services/
│
├── crm/
│
├── manage.py
└── ...
```

The structure may evolve as additional modules are implemented.

---

## Development Approach

The project is being developed incrementally with emphasis on:

* Clear separation of responsibilities
* Reusable components
* Explicit business rules
* Tenant isolation
* Database integrity
* Service-layer business logic
* Maintainable Django code
* Gradual improvement through refactoring

The project is intentionally being built as a larger application rather than as a collection of small tutorial projects.

---

## Current Status

### Completed / Implemented

* Core Django project structure
* Workspace-based tenancy foundation
* Workspace context handling
* Tenant-aware base model
* Custom QuerySets and Managers
* Soft-delete infrastructure
* Authorization foundation
* Inventory domain models
* Inventory selectors
* Inventory service layer
* Inventory business rules and validation

### In Progress

* CRM module
* Additional business workflows
* Automated tests
* Documentation
* User interface improvements

### Planned

* Remaining business modules
* Expanded automated test coverage
* Production deployment
* API layer
* Additional documentation

---

## Why This Project?

This project is being developed to gain practical experience in designing and implementing a production-oriented Django application.

Rather than focusing only on individual Django features, the project explores how those features work together in a larger application involving:

* Multi-tenancy
* Data isolation
* Authentication and authorization
* Database modeling
* Business logic
* Service architecture
* Reusable modules
* Validation
* Maintainability

---

## Project Status

This is an **ongoing portfolio project** and is not yet a finished production SaaS product.

Features, architecture, and project structure may continue to evolve during development.
