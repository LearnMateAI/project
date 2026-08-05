from mcq_generator import QuestionGeneratorLocal

def main():
    """Example usage of Local CPU Question Generator"""
    
    # Initialize the generator (this will download ~4GB the first time)
    generator = QuestionGeneratorLocal()
    
    # Sri Lankan Constitution text
    text = """
    The Constitution of the Democratic Socialist Republic of Sri Lanka is the supreme law of the country and provides the legal framework for the organization and functioning of the government. The current Constitution came into effect on 7 September 1978, replacing the 1972 Constitution and introducing an Executive Presidential System, in which the President serves as both the Head of State and the Head of Government. The Constitution declares Sri Lanka to be a sovereign, independent, unitary, and democratic republic, and establishes three main branches of government: the Executive, responsible for implementing laws; the Legislature (Parliament), responsible for making laws; and the Judiciary, responsible for interpreting laws and ensuring justice. It guarantees a range of Fundamental Rights, including equality before the law, freedom of speech and expression, freedom of religion, freedom of movement, and protection from arbitrary arrest and discrimination. The Constitution also outlines the Directive Principles of State Policy, which guide the government in promoting social welfare and economic development, and specifies the Fundamental Duties of citizens, such as protecting public property and preserving national heritage. It recognizes Sinhala and Tamil as the official languages, while English serves as the link language for communication and administration. Since its adoption, the Constitution has been amended several times through constitutional amendments to address issues such as electoral reforms, the powers of the President, the independence of public institutions, and the strengthening of democratic governance. As the highest law of the land, any law or government action that conflicts with the Constitution can be challenged and declared invalid by the courts, ensuring that the Constitution remains the foundation of Sri Lanka's legal and political system.
    """
    
    # Generate 5 Short Answer Questions locally
    print("\nStarting generation...")
    questions = generator.generate_short_answer_questions(
        text=text,
        num_questions=5,
        max_new_tokens=512,
        temperature=0.7
    )
    
    # Display the questions
    print("\n" + "="*80)
    print("GENERATED SHORT ANSWER QUESTIONS (100% OFFLINE)")
    print("="*80)
    
    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}. {q.get('question', 'No question provided')}")
        print(f"Answer: {q.get('answer', 'N/A')}")

if __name__ == "__main__":
    main()
