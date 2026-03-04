public class DocumentPrinter {
    public void printInvoice(Invoice invoice) {
        // --- Cloned Code Fragment ---
        System.out.println("*****************************");
        System.out.println("*** Company X Official ***");
        System.out.println("Date: " + java.time.LocalDate.now());
        System.out.println("*****************************");
        // ----------------------------
        
        System.out.println("Invoice Amount: $" + invoice.getTotal());
        System.out.println("Due Date: " + invoice.getDueDate());
    }

    public void printReceipt(Receipt receipt) {
        // --- Cloned Code Fragment ---
        System.out.println("*****************************");
        System.out.println("*** Company X Official ***");
        System.out.println("Date: " + java.time.LocalDate.now());
        System.out.println("*****************************");
        // ----------------------------
        
        System.out.println("Receipt Amount Paid: $" + receipt.getTotal());
        System.out.println("Payment Method: " + receipt.getMethod());
    }
}
