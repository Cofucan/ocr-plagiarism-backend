"""
Seed data for the plagiarism detection database.
Contains sample academic documents for the reference repository.
"""

from sqlalchemy.orm import Session

from app.models import Document


# Sample academic documents covering various subjects
SAMPLE_DOCUMENTS = [
    # Biology
    {
        "title": "Mitochondria - The Powerhouse of the Cell",
        "category": "Biology",
        "source": "Wikipedia",
        "content": """
        The mitochondria is the powerhouse of the cell. It is a double-membrane-bound
        organelle found in most eukaryotic organisms. Mitochondria generate most of the
        cell's supply of adenosine triphosphate (ATP), used as a source of chemical energy.
        Mitochondria were first discovered by Albert von Kölliker in 1857. The organelle
        is composed of compartments that carry out specialized functions. These compartments
        include the outer membrane, intermembrane space, inner membrane, cristae, and matrix.
        Mitochondrial DNA is inherited only from the mother. The number of mitochondria in
        a cell can vary widely by organism, tissue, and cell type. Red blood cells have no
        mitochondria, whereas liver cells can have more than 2000.
        """,
    },
    {
        "title": "Cell Division and Mitosis",
        "category": "Biology",
        "source": "Academic Textbook",
        "content": """
        Cell division is the process by which a parent cell divides into two or more
        daughter cells. Mitosis is a type of cell division that results in two daughter
        cells each having the same number and kind of chromosomes as the parent nucleus.
        The process consists of four main stages: prophase, metaphase, anaphase, and
        telophase. During prophase, chromatin condenses into chromosomes. In metaphase,
        chromosomes align at the cell equator. Anaphase involves the separation of sister
        chromatids. Finally, telophase sees the formation of two new nuclei. Cytokinesis
        typically occurs alongside telophase, dividing the cytoplasm between the two cells.
        """,
    },
    # Computer Science
    {
        "title": "Introduction to Data Structures",
        "category": "Computer Science",
        "source": "Academic Textbook",
        "content": """
        Data structures are specialized formats for organizing, processing, retrieving,
        and storing data. Common data structures include arrays, linked lists, stacks,
        queues, trees, and graphs. Arrays store elements in contiguous memory locations
        and provide constant-time access by index. Linked lists consist of nodes where
        each node contains data and a reference to the next node. Stacks follow the
        Last-In-First-Out (LIFO) principle, while queues follow First-In-First-Out (FIFO).
        Binary trees are hierarchical structures where each node has at most two children.
        The choice of data structure depends on the specific requirements of the application,
        including time complexity for operations and memory usage.
        """,
    },
    {
        "title": "Algorithm Complexity and Big O Notation",
        "category": "Computer Science",
        "source": "Wikipedia",
        "content": """
        Big O notation is a mathematical notation that describes the limiting behavior of
        a function when the argument tends towards a particular value or infinity. In
        computer science, it is used to classify algorithms according to how their run
        time or space requirements grow as the input size grows. Common time complexities
        include O(1) for constant time, O(log n) for logarithmic time, O(n) for linear time,
        O(n log n) for linearithmic time, O(n²) for quadratic time, and O(2^n) for exponential
        time. Understanding algorithmic complexity is crucial for writing efficient code
        and optimizing performance in software development.
        """,
    },
    # Physics
    {
        "title": "Newton's Laws of Motion",
        "category": "Physics",
        "source": "Academic Textbook",
        "content": """
        Newton's laws of motion are three physical laws that together laid the foundation
        for classical mechanics. The first law, also known as the law of inertia, states
        that an object at rest stays at rest and an object in motion stays in motion with
        the same speed and direction unless acted upon by an unbalanced force. The second
        law states that the acceleration of an object depends on the net force acting upon
        it and the mass of the object (F = ma). The third law states that for every action,
        there is an equal and opposite reaction. These laws were first published by Isaac
        Newton in his work Philosophiæ Naturalis Principia Mathematica in 1687.
        """,
    },
    {
        "title": "Laws of Thermodynamics",
        "category": "Physics",
        "source": "Wikipedia",
        "content": """
        The laws of thermodynamics define fundamental physical quantities such as temperature,
        energy, and entropy that characterize thermodynamic systems. The zeroth law states
        that if two systems are in thermal equilibrium with a third system, they are in
        thermal equilibrium with each other. The first law states that energy cannot be
        created or destroyed, only transformed from one form to another. The second law
        states that the total entropy of an isolated system can never decrease over time.
        The third law states that as temperature approaches absolute zero, the entropy of
        a system approaches a minimum value. These laws have profound implications for
        understanding energy transfer and the direction of natural processes.
        """,
    },
    # Engineering
    {
        "title": "Basic Circuit Analysis",
        "category": "Engineering",
        "source": "Academic Textbook",
        "content": """
        Circuit analysis is the process of finding the voltages across, and the currents
        through, all components in an electrical circuit. Ohm's Law states that the current
        through a conductor between two points is directly proportional to the voltage
        across the two points (V = IR). Kirchhoff's Current Law states that the sum of
        currents entering a node equals the sum of currents leaving that node. Kirchhoff's
        Voltage Law states that the sum of all voltages around any closed loop equals zero.
        These fundamental principles form the basis for analyzing both simple and complex
        electrical circuits. Common circuit elements include resistors, capacitors, and
        inductors, each with unique voltage-current relationships.
        """,
    },
    # Thesis Abstracts
    {
        "title": "Machine Learning Applications in Healthcare",
        "category": "Thesis Abstract",
        "source": "FUTO Repository",
        "content": """
        This research investigates the application of machine learning algorithms in
        healthcare diagnostics. The study focuses on developing predictive models for
        early disease detection using patient data. Various supervised learning techniques
        including decision trees, random forests, and neural networks were implemented
        and compared. The dataset comprised medical records from 10,000 patients over a
        five-year period. Results demonstrate that ensemble methods achieved the highest
        accuracy of 94.7% in predicting cardiovascular diseases. The research contributes
        to the growing field of medical informatics and provides a framework for
        implementing AI-assisted diagnostic tools in Nigerian healthcare facilities.
        """,
    },
    {
        "title": "Renewable Energy Solutions for Rural Nigeria",
        "category": "Thesis Abstract",
        "source": "FUTO Repository",
        "content": """
        This thesis examines sustainable energy solutions for rural communities in
        Nigeria facing electricity access challenges. The research evaluates solar,
        wind, and micro-hydro power systems for off-grid applications. A case study
        was conducted in three villages in Imo State, assessing energy needs, resource
        availability, and economic feasibility. Findings indicate that solar photovoltaic
        systems offer the most viable solution with a payback period of 3.5 years. The
        study proposes a hybrid solar-battery system capable of providing 5kWh daily
        power to households. Implementation guidelines and policy recommendations for
        scaling renewable energy adoption in rural Nigeria are presented.
        """,
    },
    {
        "title": "Software Engineering Best Practices",
        "category": "Computer Science",
        "source": "Academic Textbook",
        "content": """
        Software engineering best practices encompass methodologies and techniques for
        developing high-quality software systems. The software development life cycle
        includes requirements gathering, design, implementation, testing, deployment,
        and maintenance phases. Agile methodologies emphasize iterative development,
        collaboration, and responding to change. Version control systems like Git enable
        teams to track changes and collaborate effectively. Code reviews improve code
        quality and knowledge sharing. Unit testing and continuous integration ensure
        software reliability. Documentation is essential for maintainability. Following
        coding standards and design patterns leads to cleaner, more maintainable code.
        These practices collectively contribute to successful software project delivery.
        """,
    },
]


def seed_database(db: Session) -> int:
    """
    Seed the database with sample academic documents.

    Args:
        db: Database session

    Returns:
        Number of documents inserted
    """
    # Check if documents already exist
    existing_count = db.query(Document).count()
    if existing_count > 0:
        print(f"Database already contains {existing_count} documents. Skipping seed.")
        return 0

    # Insert sample documents
    inserted = 0
    for doc_data in SAMPLE_DOCUMENTS:
        document = Document(
            title=doc_data["title"],
            content=doc_data["content"].strip(),
            category=doc_data["category"],
            source=doc_data.get("source"),
        )
        db.add(document)
        inserted += 1

    db.commit()
    print(f"Successfully seeded {inserted} documents into the database.")
    return inserted


def clear_database(db: Session) -> int:
    """
    Clear all documents from the database.

    Args:
        db: Database session

    Returns:
        Number of documents deleted
    """
    deleted = db.query(Document).delete()
    db.commit()
    print(f"Deleted {deleted} documents from the database.")
    return deleted
